impl TypeLayout for NativeTypeLayout {
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
