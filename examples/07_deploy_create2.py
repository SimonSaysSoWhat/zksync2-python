import os
from pathlib import Path
from eth_account import Account
from eth_account.signers.local import LocalAccount
from examples.utils import EnvPrivateKey
from zksync2.core.types import EthBlockParams
from zksync2.manage_contracts.contract_encoder_base import ContractEncoder
from zksync2.manage_contracts.precompute_contract_deployer import PrecomputeContractDeployer
from zksync2.module.module_builder import ZkSyncBuilder
from zksync2.signer.eth_signer import PrivateKeyEthSigner
from zksync2.transaction.transaction_builders import TxCreate2Contract

ZKSYNC_TEST_URL = "http://127.0.0.1:3050"
ETH_TEST_URL = "http://127.0.0.1:8545"


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def generate_random_salt() -> bytes:
    return os.urandom(32)


def deploy_create2(contract: Path):
    env = EnvPrivateKey("ZKSYNC_TEST_KEY")
    web3 = ZkSyncBuilder.build(ZKSYNC_TEST_URL)
    account: LocalAccount = Account.from_key(env.key())
    chain_id = web3.zksync.chain_id
    signer = PrivateKeyEthSigner(account, chain_id)

    random_salt = generate_random_salt()
    nonce = web3.zksync.get_transaction_count(account.address, EthBlockParams.PENDING.value)
    gas_price = web3.zksync.gas_price
    deployer = PrecomputeContractDeployer(web3)

    counter_contract_encoder = ContractEncoder.from_json(web3, contract)
    precomputed_address = deployer.compute_l2_create2_address(sender=account.address,
                                                              bytecode=counter_contract_encoder.bytecode,
                                                              constructor=b'',
                                                              salt=random_salt)
    create2_contract = TxCreate2Contract(web3=web3,
                                         chain_id=chain_id,
                                         nonce=nonce,
                                         from_=account.address,
                                         gas_limit=0,
                                         gas_price=gas_price,
                                         bytecode=counter_contract_encoder.bytecode,
                                         salt=random_salt)
    estimate_gas = web3.zksync.eth_estimate_gas(create2_contract.tx)
    print(f"Fee for transaction is: {estimate_gas * gas_price}")

    tx_712 = create2_contract.tx712(estimate_gas)
    singed_message = signer.sign_typed_data(tx_712.to_eip712_struct())
    msg = tx_712.encode(singed_message)
    tx_hash = web3.zksync.send_raw_transaction(msg)
    tx_receipt = web3.zksync.wait_for_transaction_receipt(tx_hash, timeout=240, poll_latency=1.0)

    print(f"Tx status: {tx_receipt['status']}")
    contract_address = tx_receipt["contractAddress"]
    print(f"contract address: {contract_address}")
    if precomputed_address.lower() == contract_address.lower():
        print(f"{Colors.OKGREEN}Precomputed address is eqaul to deployed: {contract_address}{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}Precomputed address does not equal to deployed{Colors.ENDC}")

    value = counter_contract_encoder.contract.functions.get().call(
        {
            "from": account.address,
            "to": contract_address
        })
    print(f"Call method for deployed contract, address: {contract_address}, value: {value}")


if __name__ == "__main__":
    contract_path = Path("../tests/contracts/Counter.json")
    deploy_create2(contract_path)
