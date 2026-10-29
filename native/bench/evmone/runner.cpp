// Runs one state-test case through evmone's state transition, reading the
// binary case format of FeVM's conformance driver (native/conformance/run.py)
// from stdin and taking the driver's arguments: `RUNS [TRANSACT]` first
// decodes the case and builds its pre-state RUNS more times, applying the
// transaction to each one unless TRANSACT is 0. The last run prints its
// outcome.
#include <evmone/evmone.h>
#include <test/state/hash_utils.hpp>
#include <test/state/state.hpp>
#include <test/utils/statetest.hpp>
#include <test/utils/test_state.hpp>
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <limits>
#include <optional>
#include <string>

using namespace evmone;
using evmc::address;
using evmc::bytes32;
using intx::uint256;

namespace
{
// Cancun's blob gas limit: six blobs.
constexpr int64_t MAX_BLOB_GAS = 6 * 131072;

struct Reader
{
    const bytes& data;
    size_t position = 0;

    bytes_view take(size_t len)
    {
        const auto view = bytes_view{data}.substr(position, len);
        position += len;
        return view;
    }

    uint256 word(size_t len)
    {
        uint8_t buffer[32]{};
        const auto view = take(len);
        std::copy(view.begin(), view.end(), buffer + 32 - len);
        return intx::be::load<uint256>(buffer);
    }

    bytes32 word32() { return intx::be::store<bytes32>(word(32)); }

    address addr()
    {
        address result;
        const auto view = take(20);
        std::copy(view.begin(), view.end(), result.bytes);
        return result;
    }

    size_t count() { return static_cast<size_t>(word(4)); }
};

struct Case
{
    state::BlockInfo block;
    test::TestState pre;
    state::Transaction tx;
};

Case decode(const bytes& data)
{
    Reader reader{data};
    if (reader.word(1) != 4)
        std::abort();
    Case result;
    auto& block = result.block;
    block.coinbase = reader.addr();
    block.number = static_cast<int64_t>(reader.word(32));
    block.timestamp = static_cast<int64_t>(reader.word(32));
    block.prev_randao = reader.word32();
    block.gas_limit = static_cast<int64_t>(reader.word(32));
    block.base_fee = static_cast<uint64_t>(reader.word(32));
    block.blob_base_fee = reader.word(32);
    block.chain_id = static_cast<uint64_t>(reader.word(32));
    // evmone applies the EIP-7825 cap from Osaka, and this runner executes Cancun.
    reader.word(8);
    for (auto accounts = reader.count(); accounts != 0; --accounts)
    {
        auto& account = result.pre[reader.addr()];
        account.balance = reader.word(32);
        account.nonce = static_cast<uint64_t>(reader.word(32));
        account.code = bytes{reader.take(reader.count())};
        account.code_hash = keccak256(account.code);
        for (auto slots = reader.count(); slots != 0; --slots)
        {
            const auto slot = reader.word32();
            account.storage[slot] = reader.word32();
        }
    }
    auto& tx = result.tx;
    tx.type = static_cast<state::Transaction::Type>(static_cast<uint8_t>(reader.word(1)));
    const auto signed_chain = reader.word(1) == 1;
    tx.chain_id = static_cast<uint64_t>(reader.word(32));
    // evmone takes a legacy transaction's v of 35 or more as signing a chain ID.
    if (signed_chain && tx.type == state::Transaction::Type::legacy)
        tx.v = 35;
    tx.sender = reader.addr();
    const auto creates = reader.word(1) == 1;
    const auto to = reader.addr();
    if (!creates)
        tx.to = to;
    tx.nonce = static_cast<uint64_t>(reader.word(32));
    tx.gas_limit = static_cast<int64_t>(reader.word(8));
    tx.max_gas_price = reader.word(32);
    const auto priority_fee = reader.word(32);
    tx.max_priority_gas_price =
        tx.type >= state::Transaction::Type::eip1559 ? priority_fee : tx.max_gas_price;
    tx.max_blob_gas_price = reader.word(32);
    tx.value = reader.word(32);
    tx.data = bytes{reader.take(reader.count())};
    for (auto entries = reader.count(); entries != 0; --entries)
    {
        auto& [address, keys] = tx.access_list.emplace_back(reader.addr(), std::vector<bytes32>{});
        for (auto n = reader.count(); n != 0; --n)
            keys.push_back(reader.word32());
    }
    for (auto blobs = reader.count(); blobs != 0; --blobs)
        tx.blob_hashes.push_back(reader.word32());
    // Out-of-range nonces and y parities saturate, which keeps them invalid.
    for (auto authorizations = reader.count(); authorizations != 0; --authorizations)
    {
        auto& auth = tx.authorization_list.emplace_back();
        auth.chain_id = reader.word(32);
        auth.addr = reader.addr();
        const auto nonce = reader.word(32);
        auth.nonce = nonce > std::numeric_limits<uint64_t>::max() ?
                         std::numeric_limits<uint64_t>::max() :
                         static_cast<uint64_t>(nonce);
        const auto y_parity = reader.word(32);
        auth.y_parity = y_parity > 0xff ? uint8_t{0xff} : static_cast<uint8_t>(y_parity);
        auth.r = reader.word(32);
        auth.s = reader.word(32);
    }
    if (reader.position != data.size())
        std::abort();
    return result;
}
}  // namespace

int main(int argc, char* argv[])
{
    const uint64_t runs = argc > 1 ? std::stoull(argv[1]) : 0;
    const bool execute = argc > 2 ? std::stoull(argv[2]) != 0 : true;
    const bytes data{std::istreambuf_iterator<char>{std::cin}, std::istreambuf_iterator<char>{}};
    evmc::VM vm{evmc_create_evmone()};
    const test::TestBlockHashes block_hashes;
    // An invalid transaction has no receipt.
    const auto apply = [&](const Case& c) -> std::optional<state::TransactionReceipt> {
        const auto props = state::validate_transaction(
            c.pre, c.block, c.tx, EVMC_CANCUN, c.block.gas_limit, c.block.gas_limit, MAX_BLOB_GAS);
        if (std::holds_alternative<std::error_code>(props))
            return std::nullopt;
        return state::transition(c.pre, c.block, block_hashes, c.tx, EVMC_CANCUN, vm,
            std::get<state::TransactionProperties>(props));
    };
    // Every repeated application must use the gas the reported one does.
    std::optional<std::optional<int64_t>> repeated_gas;
    for (uint64_t run = 0; run != runs; ++run)
    {
        const auto c = decode(data);
        if (!execute)
        {
            asm volatile("" : : "r"(&c) : "memory");
            continue;
        }
        const auto receipt = apply(c);
        const auto gas = receipt ? std::optional{receipt->gas_used} : std::nullopt;
        if (repeated_gas && *repeated_gas != gas)
            std::abort();
        repeated_gas = gas;
    }
    const auto c = decode(data);
    const auto receipt = apply(c);
    if (!receipt)
    {
        if (repeated_gas && repeated_gas->has_value())
            std::abort();
        std::cout << R"({"invalid":1})" << '\n';
        return 0;
    }
    if (repeated_gas && *repeated_gas != receipt->gas_used)
        std::abort();
    const auto status = receipt->status == EVMC_SUCCESS ? std::string{"success"} :
                        receipt->status == EVMC_REVERT  ? std::string{"revert"} :
                                                          "halt " + std::to_string(receipt->status);
    const auto logs_hash = test::logs_hash(receipt->logs);
    std::cout << R"({"invalid":0,"status":")" << status << R"(","gas_used":)" << receipt->gas_used
              << R"(,"logs_hash":"0x)" << evmc::hex({logs_hash.bytes, sizeof(logs_hash.bytes)})
              << "\"}\n";
}
