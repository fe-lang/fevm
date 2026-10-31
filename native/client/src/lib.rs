//! A client for `fevm serve`: one fevm process holding one world, driven by
//! length-prefixed binary requests over its stdin and stdout. See README.md for
//! the protocol.

use std::{
    fmt,
    io::{self, BufReader, BufWriter, Read, Write},
    path::Path,
    process::{Child, ChildStdin, ChildStdout, Command, Stdio},
};

/// A 256-bit word, big endian.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct U256(pub [u8; 32]);

impl From<u64> for U256 {
    fn from(value: u64) -> Self {
        U256::from(u128::from(value))
    }
}

impl From<u128> for U256 {
    fn from(value: u128) -> Self {
        let mut word = [0; 32];
        word[16..].copy_from_slice(&value.to_be_bytes());
        U256(word)
    }
}

impl U256 {
    /// The low 128 bits, if the word fits in them.
    pub fn to_u128(self) -> Option<u128> {
        let (high, low) = self.0.split_at(16);
        high.iter()
            .all(|&byte| byte == 0)
            .then(|| u128::from_be_bytes(low.try_into().expect("16 bytes")))
    }
}

/// A 20-byte account address.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Address(pub [u8; 20]);

impl From<u64> for Address {
    fn from(value: u64) -> Self {
        let mut address = [0; 20];
        address[12..].copy_from_slice(&value.to_be_bytes());
        Address(address)
    }
}

/// Host settings. `Config::osaka()` is mainnet's rules.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Config {
    pub max_code_size: u64,
    pub max_initcode_size: u64,
    pub tx_gas_limit_cap: u64,
    pub check_chain_id: bool,
    pub check_nonce: bool,
    pub check_base_fee: bool,
    pub check_sender_code: bool,
}

impl Config {
    pub fn osaka() -> Self {
        Config {
            max_code_size: 24_576,
            max_initcode_size: 49_152,
            tx_gas_limit_cap: 1 << 24,
            check_chain_id: true,
            check_nonce: true,
            check_base_fee: true,
            check_sender_code: true,
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Config::osaka()
    }
}

/// The block's values that transactions see.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Block {
    pub coinbase: Address,
    pub number: U256,
    pub timestamp: U256,
    pub prevrandao: U256,
    pub gas_limit: U256,
    pub base_fee: U256,
    pub blob_base_fee: U256,
    pub chain_id: U256,
}

/// A transaction envelope's type.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum TxKind {
    #[default]
    Legacy = 0,
    AccessList = 1,
    FeeMarket = 2,
    Blob = 3,
    SetCode = 4,
}

/// An EIP-7702 authorization, with its signature.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Authorization {
    pub chain_id: U256,
    pub address: Address,
    pub nonce: U256,
    pub y_parity: U256,
    pub r: U256,
    pub s: U256,
}

/// A transaction from a recovered sender. `to: None` creates a contract from
/// `data`. `gas_price` is the legacy price or the EIP-1559 maximum fee.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Tx {
    pub kind: TxKind,
    pub chain_id: Option<U256>,
    pub sender: Address,
    pub to: Option<Address>,
    pub nonce: U256,
    pub gas_limit: u64,
    pub gas_price: U256,
    pub max_priority_fee_per_gas: U256,
    pub max_fee_per_blob_gas: U256,
    pub value: U256,
    pub data: Vec<u8>,
    pub access_list: Vec<(Address, Vec<U256>)>,
    pub blob_hashes: Vec<U256>,
    pub authorizations: Vec<Authorization>,
}

/// How a transaction's execution ended. Exceptional halts consume all gas;
/// host failures leave the pre-state.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Success,
    Revert,
    StackUnderflow,
    StackOverflow,
    OutOfGas,
    InvalidJump,
    InvalidOpcode,
    ReturnDataOutOfBounds,
    StaticWrite,
    CodePrefix,
    PrecompileFailure,
    AddressCollision,
    HostAllocation,
    BalanceOverflow,
    Unknown(u8),
}

impl Status {
    fn from_code(code: u8) -> Self {
        match code {
            0 => Status::Success,
            19 => Status::Revert,
            10 => Status::StackUnderflow,
            11 => Status::StackOverflow,
            15 => Status::OutOfGas,
            16 => Status::InvalidJump,
            17 => Status::InvalidOpcode,
            18 => Status::ReturnDataOutOfBounds,
            23 => Status::StaticWrite,
            24 => Status::CodePrefix,
            25 => Status::PrecompileFailure,
            27 => Status::AddressCollision,
            21 => Status::HostAllocation,
            26 => Status::BalanceOverflow,
            code => Status::Unknown(code),
        }
    }
}

/// Why a transaction is not includable.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Invalid {
    IntrinsicGas,
    InitcodeSize,
    NonceLimit,
    PriorityFee,
    GasLimit,
    BlobCount,
    FeeCap,
    Create,
    NoBlobs,
    BlobVersion,
    BlobFeeCap,
    Nonce,
    Balance,
    SenderCode,
    TxType,
    GasLimitCap,
    ChainId,
    NoAuthorizations,
    Unknown(u8),
}

impl Invalid {
    fn from_code(code: u8) -> Option<Self> {
        Some(match code {
            0 => return None,
            1 => Invalid::IntrinsicGas,
            2 => Invalid::InitcodeSize,
            3 => Invalid::NonceLimit,
            4 => Invalid::PriorityFee,
            5 => Invalid::GasLimit,
            6 => Invalid::BlobCount,
            7 => Invalid::FeeCap,
            8 => Invalid::Create,
            9 => Invalid::NoBlobs,
            10 => Invalid::BlobVersion,
            11 => Invalid::BlobFeeCap,
            12 => Invalid::Nonce,
            13 => Invalid::Balance,
            14 => Invalid::SenderCode,
            15 => Invalid::TxType,
            16 => Invalid::GasLimitCap,
            17 => Invalid::ChainId,
            18 => Invalid::NoAuthorizations,
            code => Invalid::Unknown(code),
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Log {
    pub address: Address,
    pub topics: Vec<U256>,
    pub data: Vec<u8>,
}

/// A transaction's result. An invalid transaction ran nothing; its other
/// fields are empty.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Receipt {
    pub invalid: Option<Invalid>,
    pub status: Status,
    pub gas_used: u64,
    pub gas_refunded: u64,
    pub created: Option<Address>,
    pub output: Vec<u8>,
    pub logs: Vec<Log>,
}

impl Receipt {
    pub fn succeeded(&self) -> bool {
        self.invalid.is_none() && self.status == Status::Success
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Account {
    pub exists: bool,
    pub balance: U256,
    pub nonce: U256,
    pub code_hash: U256,
    pub code: Vec<u8>,
}

#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    /// fevm could not allocate memory for the request.
    Allocation,
    /// fevm could not parse the request.
    BadRequest,
    /// The snapshot id was never taken, or a revert discarded it.
    NoSnapshot,
    /// fevm answered with something this client does not understand.
    Protocol(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Error::Io(error) => write!(f, "fevm I/O: {error}"),
            Error::Allocation => write!(f, "fevm could not allocate memory"),
            Error::BadRequest => write!(f, "fevm rejected a malformed request"),
            Error::NoSnapshot => write!(f, "no such snapshot"),
            Error::Protocol(message) => write!(f, "fevm protocol: {message}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<io::Error> for Error {
    fn from(error: io::Error) -> Self {
        Error::Io(error)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

const CONFIGURE: u8 = 1;
const SET_BLOCK: u8 = 2;
const SET_BALANCE: u8 = 3;
const SET_NONCE: u8 = 4;
const SET_CODE: u8 = 5;
const SET_STORAGE: u8 = 6;
const SET_BLOCK_HASH: u8 = 7;
const ACCOUNT: u8 = 8;
const STORAGE: u8 = 9;
const TRANSACT: u8 = 10;
const SNAPSHOT: u8 = 11;
const REVERT: u8 = 12;

const COMMIT: u8 = 1;

struct Encoder(Vec<u8>);

impl Encoder {
    fn new(command: u8) -> Self {
        Encoder(vec![command])
    }

    fn byte(&mut self, value: u8) -> &mut Self {
        self.0.push(value);
        self
    }

    fn word(&mut self, value: U256) -> &mut Self {
        self.0.extend_from_slice(&value.0);
        self
    }

    fn address(&mut self, value: Address) -> &mut Self {
        self.0.extend_from_slice(&value.0);
        self
    }

    fn u64(&mut self, value: u64) -> &mut Self {
        self.0.extend_from_slice(&value.to_be_bytes());
        self
    }

    fn count(&mut self, count: usize) -> &mut Self {
        let count = u32::try_from(count).expect("fevm frames hold at most 2^32 - 1 items");
        self.0.extend_from_slice(&count.to_be_bytes());
        self
    }

    fn bytes(&mut self, bytes: &[u8]) -> &mut Self {
        self.count(bytes.len());
        self.0.extend_from_slice(bytes);
        self
    }
}

struct Decoder<'a>(&'a [u8]);

impl<'a> Decoder<'a> {
    fn take(&mut self, len: usize) -> Result<&'a [u8]> {
        if self.0.len() < len {
            return Err(Error::Protocol("response ended early".into()));
        }
        let (taken, rest) = self.0.split_at(len);
        self.0 = rest;
        Ok(taken)
    }

    fn byte(&mut self) -> Result<u8> {
        Ok(self.take(1)?[0])
    }

    fn word(&mut self) -> Result<U256> {
        Ok(U256(self.take(32)?.try_into().expect("32 bytes")))
    }

    fn address(&mut self) -> Result<Address> {
        Ok(Address(self.take(20)?.try_into().expect("20 bytes")))
    }

    fn u64(&mut self) -> Result<u64> {
        Ok(u64::from_be_bytes(
            self.take(8)?.try_into().expect("8 bytes"),
        ))
    }

    fn count(&mut self) -> Result<usize> {
        Ok(u32::from_be_bytes(self.take(4)?.try_into().expect("4 bytes")) as usize)
    }

    fn bytes(&mut self) -> Result<Vec<u8>> {
        let len = self.count()?;
        Ok(self.take(len)?.to_vec())
    }

    fn finish(self) -> Result<()> {
        if self.0.is_empty() {
            Ok(())
        } else {
            Err(Error::Protocol(format!(
                "{} unread response bytes",
                self.0.len()
            )))
        }
    }
}

/// One `fevm serve` process and the world it holds.
pub struct Session {
    child: Child,
    // Taken when the session drops: closing stdin ends fevm serve.
    input: Option<BufWriter<ChildStdin>>,
    output: BufReader<ChildStdout>,
}

impl Session {
    /// Starts `fevm serve` with an empty world, a zeroed block and Osaka
    /// settings.
    pub fn spawn(fevm: impl AsRef<Path>) -> io::Result<Self> {
        let mut child = Command::new(fevm.as_ref())
            .arg("serve")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()?;
        let input = Some(BufWriter::new(child.stdin.take().expect("piped stdin")));
        let output = BufReader::new(child.stdout.take().expect("piped stdout"));
        Ok(Session {
            child,
            input,
            output,
        })
    }

    /// Sends one request and returns the response after its status.
    fn request(&mut self, request: &Encoder) -> Result<Vec<u8>> {
        let len = u32::try_from(request.0.len()).expect("requests stay below 4 GiB");
        let input = self.input.as_mut().expect("open until the session drops");
        input.write_all(&len.to_be_bytes())?;
        input.write_all(&request.0)?;
        input.flush()?;
        let mut header = [0; 4];
        self.output.read_exact(&mut header)?;
        let mut response = vec![0; u32::from_be_bytes(header) as usize];
        self.output.read_exact(&mut response)?;
        match response.first() {
            Some(0) => Ok(response.split_off(1)),
            Some(1) => Err(Error::Allocation),
            Some(2) => Err(Error::BadRequest),
            Some(3) => Err(Error::NoSnapshot),
            Some(status) => Err(Error::Protocol(format!("unknown response status {status}"))),
            None => Err(Error::Protocol("empty response".into())),
        }
    }

    fn done(&mut self, request: &Encoder) -> Result<()> {
        Decoder(&self.request(request)?).finish()
    }

    pub fn configure(&mut self, config: &Config) -> Result<()> {
        let checks = [
            config.check_chain_id,
            config.check_nonce,
            config.check_base_fee,
            config.check_sender_code,
        ]
        .iter()
        .enumerate()
        .fold(0, |bits, (bit, &on)| bits | (u8::from(on) << bit));
        self.done(
            Encoder::new(CONFIGURE)
                .u64(config.max_code_size)
                .u64(config.max_initcode_size)
                .u64(config.tx_gas_limit_cap)
                .byte(checks),
        )
    }

    pub fn set_block(&mut self, block: &Block) -> Result<()> {
        self.done(
            Encoder::new(SET_BLOCK)
                .address(block.coinbase)
                .word(block.number)
                .word(block.timestamp)
                .word(block.prevrandao)
                .word(block.gas_limit)
                .word(block.base_fee)
                .word(block.blob_base_fee)
                .word(block.chain_id),
        )
    }

    pub fn set_balance(&mut self, address: Address, balance: U256) -> Result<()> {
        self.done(Encoder::new(SET_BALANCE).address(address).word(balance))
    }

    pub fn set_nonce(&mut self, address: Address, nonce: U256) -> Result<()> {
        self.done(Encoder::new(SET_NONCE).address(address).word(nonce))
    }

    pub fn set_code(&mut self, address: Address, code: &[u8]) -> Result<()> {
        self.done(Encoder::new(SET_CODE).address(address).bytes(code))
    }

    pub fn set_storage(&mut self, address: Address, slot: U256, value: U256) -> Result<()> {
        self.done(
            Encoder::new(SET_STORAGE)
                .address(address)
                .word(slot)
                .word(value),
        )
    }

    /// The hash BLOCKHASH returns for `number`, within the last 256 blocks.
    pub fn set_block_hash(&mut self, number: U256, hash: U256) -> Result<()> {
        self.done(Encoder::new(SET_BLOCK_HASH).word(number).word(hash))
    }

    pub fn account(&mut self, address: Address) -> Result<Account> {
        let response = self.request(Encoder::new(ACCOUNT).address(address))?;
        let mut decoder = Decoder(&response);
        let account = Account {
            exists: decoder.byte()? != 0,
            balance: decoder.word()?,
            nonce: decoder.word()?,
            code_hash: decoder.word()?,
            code: decoder.bytes()?,
        };
        decoder.finish()?;
        Ok(account)
    }

    pub fn storage(&mut self, address: Address, slot: U256) -> Result<U256> {
        let response = self.request(Encoder::new(STORAGE).address(address).word(slot))?;
        let mut decoder = Decoder(&response);
        let value = decoder.word()?;
        decoder.finish()?;
        Ok(value)
    }

    /// Runs `tx` and keeps its changes.
    pub fn transact(&mut self, tx: &Tx) -> Result<Receipt> {
        self.run(tx, COMMIT)
    }

    /// Runs `tx` and keeps none of its changes, as eth_call does.
    pub fn call(&mut self, tx: &Tx) -> Result<Receipt> {
        self.run(tx, 0)
    }

    fn run(&mut self, tx: &Tx, flags: u8) -> Result<Receipt> {
        let mut request = Encoder::new(TRANSACT);
        request
            .byte(flags)
            .byte(tx.kind as u8)
            .byte(u8::from(tx.chain_id.is_some()))
            .word(tx.chain_id.unwrap_or_default())
            .address(tx.sender)
            .byte(u8::from(tx.to.is_none()))
            .address(tx.to.unwrap_or_default())
            .word(tx.nonce)
            .u64(tx.gas_limit)
            .word(tx.gas_price)
            .word(tx.max_priority_fee_per_gas)
            .word(tx.max_fee_per_blob_gas)
            .word(tx.value)
            .bytes(&tx.data)
            .count(tx.access_list.len());
        for (address, slots) in &tx.access_list {
            request.address(*address).count(slots.len());
            for &slot in slots {
                request.word(slot);
            }
        }
        request.count(tx.blob_hashes.len());
        for &hash in &tx.blob_hashes {
            request.word(hash);
        }
        request.count(tx.authorizations.len());
        for authorization in &tx.authorizations {
            request
                .word(authorization.chain_id)
                .address(authorization.address)
                .word(authorization.nonce)
                .word(authorization.y_parity)
                .word(authorization.r)
                .word(authorization.s);
        }
        let response = self.request(&request)?;
        let mut decoder = Decoder(&response);
        let invalid = Invalid::from_code(decoder.byte()?);
        let status = Status::from_code(decoder.byte()?);
        let gas_used = decoder.u64()?;
        let gas_refunded = decoder.u64()?;
        let has_created = decoder.byte()? != 0;
        let created = decoder.address()?;
        let output = decoder.bytes()?;
        let logs = (0..decoder.count()?)
            .map(|_| {
                let address = decoder.address()?;
                let topics = (0..decoder.byte()?)
                    .map(|_| decoder.word())
                    .collect::<Result<_>>()?;
                Ok(Log {
                    address,
                    topics,
                    data: decoder.bytes()?,
                })
            })
            .collect::<Result<_>>()?;
        decoder.finish()?;
        Ok(Receipt {
            invalid,
            status,
            gas_used,
            gas_refunded,
            created: has_created.then_some(created),
            output,
            logs,
        })
    }

    /// Keeps a copy of the world and returns its id. Ids count up from zero.
    pub fn snapshot(&mut self) -> Result<u32> {
        let response = self.request(&Encoder::new(SNAPSHOT))?;
        let mut decoder = Decoder(&response);
        let id = decoder.count()?;
        decoder.finish()?;
        Ok(u32::try_from(id).expect("ids are u32"))
    }

    /// Restores snapshot `id` and discards later snapshots. `id` stays, so the
    /// world can be restored to it again.
    pub fn revert(&mut self, id: u32) -> Result<()> {
        self.done(Encoder::new(REVERT).count(id as usize))
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        drop(self.input.take());
        let _ = self.child.wait();
    }
}
