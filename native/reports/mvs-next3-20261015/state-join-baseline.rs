    pub fn join(&self, ctx: &ModuleCtx, other: &Self) -> Self {
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
