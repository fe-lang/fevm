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

const GAS_LIMIT: u64 = 1_000_000;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Case {
    code: String,
    calldata: String,
}

#[derive(Debug, Serialize)]
struct Frame {
    status: &'static str,
    stack: Option<Vec<String>>,
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
        GAS_LIMIT,
    );
    let result = interpreter
        .run_plain(
            &instruction_table::<EthInterpreter, DummyHost>(),
            &mut DummyHost,
        )
        .into_result_return()
        .ok_or("nested frames are outside this corpus")?;
    let status = match result.result {
        InstructionResult::Stop | InstructionResult::Return => "success",
        InstructionResult::Revert => "revert",
        InstructionResult::StackUnderflow => "stack_underflow",
        InstructionResult::StackOverflow => "stack_overflow",
        InstructionResult::InvalidJump => "invalid_jump",
        InstructionResult::InvalidFEOpcode | InstructionResult::OpcodeNotFound => "invalid_opcode",
        other => return Err(format!("reference result outside this corpus: {other:?}").into()),
    };
    let stack = matches!(status, "success" | "revert").then(|| {
        interpreter
            .stack
            .data()
            .iter()
            .map(|word| format!("0x{word:064x}"))
            .collect()
    });
    Ok(Frame {
        status,
        stack,
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
