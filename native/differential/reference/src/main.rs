use std::error::Error;
use std::io::{self, BufRead, Write};

use revm_bytecode::Bytecode;
use revm_interpreter::host::DummyHost;
use revm_interpreter::interpreter::{EthInterpreter, ExtBytecode};
use revm_interpreter::{
    CallInput, InputsImpl, InstructionResult, Interpreter, SharedMemory, instruction_table,
};
use revm_primitives::{Bytes, hardfork::SpecId, hex};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Case {
    code: String,
    calldata: String,
    gas_limit: u64,
}

#[derive(Debug, Serialize)]
struct Frame {
    outcome: &'static str,
    reason: Option<&'static str>,
    gas_remaining: u64,
    stack: Option<Vec<String>>,
    memory: Option<String>,
    output: String,
}

fn execute(case: Case) -> Result<Frame, Box<dyn Error>> {
    let code = hex::decode(case.code)?;
    let calldata = hex::decode(case.calldata)?;
    if code.len() > 4096 || calldata.len() > 4096 {
        return Err("case exceeds the current FeVM input capacities".into());
    }
    let mut interpreter = Interpreter::<EthInterpreter>::new(
        SharedMemory::new(),
        ExtBytecode::new(Bytecode::new_legacy(Bytes::from(code))),
        InputsImpl {
            input: CallInput::Bytes(Bytes::from(calldata)),
            ..InputsImpl::default()
        },
        false,
        SpecId::CANCUN,
        case.gas_limit,
    );
    let result = interpreter
        .run_plain(
            &instruction_table::<EthInterpreter, DummyHost>(),
            &mut DummyHost,
        )
        .into_result_return()
        .ok_or("nested frames are outside this corpus")?;
    let (outcome, reason) = match result.result {
        InstructionResult::Stop | InstructionResult::Return => ("success", None),
        InstructionResult::Revert => ("revert", None),
        InstructionResult::StackUnderflow => ("exceptional", Some("stack_underflow")),
        InstructionResult::StackOverflow => ("exceptional", Some("stack_overflow")),
        InstructionResult::InvalidJump => ("exceptional", Some("invalid_jump")),
        InstructionResult::InvalidFEOpcode | InstructionResult::OpcodeNotFound => {
            ("exceptional", Some("invalid_opcode"))
        }
        InstructionResult::OutOfOffset => ("exceptional", Some("return_data_oob")),
        InstructionResult::OutOfGas
        | InstructionResult::MemoryOOG
        | InstructionResult::InvalidOperandOOG => ("exceptional", Some("out_of_gas")),
        other => return Err(format!("reference result outside this corpus: {other:?}").into()),
    };
    let completed = outcome != "exceptional";
    let stack = completed.then(|| {
        interpreter
            .stack
            .data()
            .iter()
            .map(|word| format!("0x{word:064x}"))
            .collect()
    });
    Ok(Frame {
        outcome,
        reason,
        // The outer EVM consumes all frame gas on exceptional termination.
        // Interpreter diagnostics may still contain an unspent partial budget.
        gas_remaining: if completed { result.gas.remaining() } else { 0 },
        stack,
        memory: completed.then(|| {
            format!(
                "0x{}",
                hex::encode(interpreter.memory.context_memory().as_ref())
            )
        }),
        output: format!("0x{}", hex::encode(result.output)),
    })
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut output = io::BufWriter::new(io::stdout().lock());
    for line in io::stdin().lock().lines() {
        let frame = execute(serde_json::from_str(&line?)?)?;
        serde_json::to_writer(&mut output, &frame)?;
        writeln!(output)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{Case, execute};

    #[test]
    fn reports_exact_gas_and_exceptional_frame_consumption() {
        for (gas_limit, outcome, remaining) in
            [(1, "exceptional", 0), (2, "success", 0), (3, "success", 1)]
        {
            let frame = execute(Case {
                code: "5f".into(),
                calldata: String::new(),
                gas_limit,
            })
            .unwrap();
            assert_eq!(frame.outcome, outcome);
            assert_eq!(frame.gas_remaining, remaining);
            assert_eq!(frame.stack.is_some(), outcome == "success");
            assert_eq!(frame.memory.is_some(), outcome == "success");
        }
    }

    #[test]
    fn retains_bounds_reason_when_memory_is_also_unpayable() {
        let frame = execute(Case {
            code: "600160017f80000000000000000000000000000000000000000000000000000000000000003e"
                .into(),
            calldata: String::new(),
            gas_limit: 1_000_000,
        })
        .unwrap();
        assert_eq!(frame.outcome, "exceptional");
        assert_eq!(frame.reason, Some("return_data_oob"));
        assert_eq!(frame.gas_remaining, 0);
        assert_eq!(frame.output, "0x");
    }
}
