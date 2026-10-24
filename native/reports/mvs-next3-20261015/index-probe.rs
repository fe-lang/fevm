
    #[test]
    #[ignore]
    fn benchmark_index_snapshots() {
        use std::{hint::black_box, time::Instant};
        for count in [256, 1024, 4096] {
            let mut index = ViewIndex::default();
            let facts: Vec<_> = (0..count).map(|i| {
                let id = ValueId::from_u32(i as u32);
                let mut refs = References::root(Root::Recent(ValueId::from_u32((i / 64) as u32)));
                refs.views = refs.views.into_iter().map(|mut view| {
                    view.place.path = vec![Step::Index(Index::Constant(i % 64)), Step::Payload(0, 1)];
                    view
                }).collect();
                refs.cache = Some(id);
                (id, refs)
            }).collect();
            for (id, refs) in &facts { index.update(*id, refs, true); }
            let start = Instant::now();
            for iteration in 0..512 {
                let mut snapshot = black_box(&index).clone();
                let (id, refs) = &facts[iteration % count];
                snapshot.update(*id, refs, false);
                black_box(snapshot);
            }
            println!("INDEX_PROBE count={count} iterations=512 seconds={:.9}", start.elapsed().as_secs_f64());
        }
    }
