
    #[test]
    #[ignore]
    fn compilation_join_probe() {
        use std::{hint::black_box, time::Instant};
        for depth in [2_usize, 4, 8, 12] {
            let mut source = String::from("target = \"evm-ethereum-osaka\"\n");
            source.push_str("type @L0 = { i256 };\n");
            for level in 1..depth {
                source.push_str(&format!("type @L{level} = {{ @L{} }};\n", level - 1));
            }
            source.push_str(&format!("func private %f(v0.@L{}) {{ block0: return; }}\n", depth - 1));
            let parsed = parse_module(&source).unwrap();
            let ctx = &parsed.module.ctx;
            let ty = ctx.func_sig(parsed.module.funcs()[0], |sig| sig.args()[0]);
            let mut layout = AggregateLayoutCache::default();
            let path = vec![0; depth];
            let slice = shape::aggregate_slice_for_path(ctx, ty, &path).unwrap();
            let mut left = InitializedValue::new(ty, false);
            left.put(ctx, slice, InitializedValue::new(slice.ty, true), &mut layout);
            let mut changed = left.clone();
            changed.put(ctx, slice, InitializedValue::new(slice.ty, false), &mut layout);
            for (name, right) in [("identical", &left), ("changed", &changed)] {
                let expected = name == "identical";
                assert_eq!(left.join(ctx, right).defined(ctx), expected);
                let started = Instant::now();
                for _ in 0..256 {
                    black_box(black_box(&left).join(black_box(ctx), black_box(right)));
                }
                println!("JOIN_PROBE {{\"depth\":{depth},\"case\":\"{name}\",\"iterations\":256,\"seconds\":{}}}", started.elapsed().as_secs_f64());
            }
        }
    }
