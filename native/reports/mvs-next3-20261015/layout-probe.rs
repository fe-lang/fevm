
    use crate::{module::ModuleCtx, isa::{TypeLayout, Endian}, types::CompoundType};
    struct ProbeBaselineNativeTypeLayout;
impl TypeLayout for ProbeBaselineNativeTypeLayout {
    fn size_of(&self, ty: Type, ctx: &ModuleCtx) -> Result<usize, TypeLayoutError> {
        let size = match ty {
            Type::Unit => 0,
            Type::I1 | Type::I8 => 1,
            Type::I16 => 2,
            Type::I32 => 4,
            Type::I64 => 8,
            Type::I128 => 16,
            Type::I256 => 32,
            Type::EnumTag(_) => return Err(TypeLayoutError::UnrepresentableType(ty)),
            Type::Compound(compound) => {
                match ctx.with_ty_store(|store| store.resolve_compound(compound).clone()) {
                    CompoundType::Array { elem, len } => self.size_of(elem, ctx)? * len,
                    CompoundType::Struct(data) => {
                        if data.packed {
                            return Err(TypeLayoutError::UnsupportedType(ty));
                        }
                        let mut size = 0usize;
                        let mut struct_align = 1usize;
                        for field in data.fields {
                            let align = self.align_of(field, ctx)?;
                            size = size.next_multiple_of(align);
                            size += self.size_of(field, ctx)?;
                            struct_align = struct_align.max(align);
                        }
                        size.next_multiple_of(struct_align)
                    }
                    CompoundType::Ptr(_) | CompoundType::ObjRef(_) | CompoundType::ConstRef(_) => 8,
                    CompoundType::Enum(_) | CompoundType::Func { .. } => {
                        return Err(TypeLayoutError::UnrepresentableType(ty));
                    }
                }
            }
        };
        Ok(size)
    }

    fn align_of(&self, ty: Type, ctx: &ModuleCtx) -> Result<usize, TypeLayoutError> {
        let align = match ty {
            Type::Unit | Type::I1 | Type::I8 => 1,
            Type::I16 => 2,
            Type::I32 => 4,
            Type::I64 => 8,
            Type::I128 => 16,
            Type::I256 => 16,
            Type::EnumTag(_) => return Err(TypeLayoutError::UnrepresentableType(ty)),
            Type::Compound(compound) => {
                match ctx.with_ty_store(|store| store.resolve_compound(compound).clone()) {
                    CompoundType::Array { elem, .. } => self.align_of(elem, ctx)?,
                    CompoundType::Struct(data) => {
                        if data.packed {
                            return Err(TypeLayoutError::UnsupportedType(ty));
                        }
                        let mut align = 1usize;
                        for field in data.fields {
                            align = align.max(self.align_of(field, ctx)?);
                        }
                        align
                    }
                    CompoundType::Ptr(_) | CompoundType::ObjRef(_) | CompoundType::ConstRef(_) => 8,
                    CompoundType::Enum(_) | CompoundType::Func { .. } => {
                        return Err(TypeLayoutError::UnrepresentableType(ty));
                    }
                }
            }
        };
        Ok(align)
    }

    fn pointer_repl(&self) -> Type {
        Type::I64
    }

    fn endian(&self) -> Endian {
        Endian::Le
    }
}

    #[test]
    #[ignore]
    fn benchmark_native_layout() {
        use std::{hint::black_box, time::Instant};
        let module = Module::new(&native_isa());
        for depth in [2, 6, 10] {
            let mut ty = Type::I128;
            for level in 0..depth {
                ty = module.ctx.with_ty_store_mut(|store| {
                    store.make_struct(&format!("Probe{depth}_{level}"), &[ty, Type::I8, ty], false)
                });
            }
            for pair in 0..6 {
                for name in if pair % 2 == 0 { ["baseline", "candidate"] } else { ["candidate", "baseline"] } {
                    let layout: &dyn TypeLayout = if name == "baseline" { &ProbeBaselineNativeTypeLayout } else { &super::NativeTypeLayout };
                    let start = Instant::now();
                    for _ in 0..256 {
                        black_box(layout.size_of(black_box(ty), &module.ctx).unwrap());
                        black_box(layout.align_of(black_box(ty), &module.ctx).unwrap());
                    }
                    println!("LAYOUT_PROBE depth={depth} pair={pair} compiler={name} iterations=256 seconds={:.9}", start.elapsed().as_secs_f64());
                }
            }
        }
    }
