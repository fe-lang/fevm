
    impl State {
    fn benchmark_rebuilding_join(&self, ctx: &ModuleCtx, other: &Self) -> Self {
        let mut result = Self {
            objects: self.objects.clone(),
            bound: self.bound.union(&other.bound).copied().collect(),
            ..Self::default()
        };
        // Allocation facts are conditional on that allocation existing. Phi
        // substitution occurs first, so branch-local values cannot lose their
        // guarantees merely because the other branch did not allocate them.
        for (&root, value) in &other.objects {
            result
                .objects
                .entry(root)
                .and_modify(|a| *a = a.join(ctx, value))
                .or_insert_with(|| value.clone());
        }
        for (&id, a) in &self.values {
            if let Some(b) = other.values.get(&id) {
                result.values.insert(id, a.join(ctx, b));
            }
        }
        for (&id, a) in &self.views {
            if let Some(b) = other.views.get(&id) {
                result.views.insert(
                    id,
                    ViewFact {
                        references: a.references.join(&b.references),
                        value: a.value.join(ctx, &b.value),
                        guards: a.guards && b.guards,
                    },
                );
            }
        }
        for (&id, fact) in &result.views {
            result.view_index.update(id, &fact.references, true);
        }
        for (&id, refs) in &self.observations {
            if let Some(other) = other.observations.get(&id)
                && (refs == other || refs.same_location(other))
            {
                result.observations.insert(id, refs.join(other));
            }
        }
        for (&id, relation) in &self.value_observations {
            if other.value_observations.get(&id) == Some(relation) {
                result.value_observations.insert(id, *relation);
            }
        }
        result.exposed = self.exposed.union(&other.exposed).copied().collect();
        result.close_exposure(ctx);
        result
    }

    }

    #[test]
    #[ignore]
    fn benchmark_state_index_joins() {
        use std::{hint::black_box, time::Instant};
        let module = Module::new(&Evm::new(TargetTriple::parse("evm-ethereum-cancun").unwrap()));
        for count in [128, 512, 2048] {
            let mut left = State::default();
            for i in 0..count {
                let id = ValueId::from_u32(i);
                let mut references = References::root(Root::Recent(ValueId::from_u32(i / 64)));
                references.views = references.views.into_iter().map(|mut view| {
                    view.place.path = vec![Step::Index(Index::Constant(i as usize % 64))];
                    view
                }).collect();
                references.cache = Some(id);
                left.view_index.update(id, &references, true);
                left.views.insert(id, ViewFact { references, value: ValueState::new(Type::I32, true), guards: true });
            }
            for changed in [false, true] {
                let mut right = left.clone();
                if changed {
                    let id = ValueId::from_u32(0);
                    let fact = right.views.get_mut(&id).unwrap();
                    right.view_index.update(id, &fact.references, false);
                    fact.references = References::root(Root::Recent(ValueId::from_u32(count)));
                    fact.references.cache = Some(id);
                    right.view_index.update(id, &fact.references, true);
                }
                assert_eq!(left.benchmark_rebuilding_join(&module.ctx, &right), left.join(&module.ctx, &right));
                for pair in 0..6 {
                    for name in if pair % 2 == 0 { ["baseline", "candidate"] } else { ["candidate", "baseline"] } {
                        let start = Instant::now();
                        for _ in 0..64 {
                            let joined = if name == "baseline" { left.benchmark_rebuilding_join(&module.ctx, black_box(&right)) } else { left.join(&module.ctx, black_box(&right)) };
                            black_box(joined);
                        }
                        println!("JOIN_PROBE count={count} changed={changed} pair={pair} compiler={name} iterations=64 seconds={:.9}",start.elapsed().as_secs_f64());
                    }
                }
            }
        }
    }
