"""Generate offline, reproducible Bitcoin-like observations and evaluation labels."""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

COLUMNS = ["timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
           "input_addresses", "output_addresses", "input_amounts", "output_amounts",
           "fee", "script_type"]
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SATOSHIS = 100_000_000


def btc(satoshis):
    """Format integer satoshis as an exact eight-decimal BTC string."""
    return f"{Decimal(satoshis) / SATOSHIS:.8f}"


def partition(total, count, rng):
    """Split satoshis into positive integer amounts without rounding loss."""
    cuts = [0] + sorted(rng.sample(range(1, total), count - 1)) + [total]
    return [right - left for left, right in zip(cuts, cuts[1:])]


def generate_dataset(rows=1000, seed=42):
    """Build ordinary observations plus three deliberately injected scenarios."""
    if rows < 100:
        raise ValueError("--rows must be at least 100 to keep ordinary activity the majority")
    rng = random.Random(seed)
    records = []
    truth = {"seed": seed, "rows": rows, "evaluation_only": True,
             "scenarios": {}}

    def transaction(seconds, inputs, outputs, output_values, input_values=None):
        """Append one balanced synthetic transaction with a network observation."""
        fee = rng.randint(200, 2500) * (len(inputs) + len(outputs))
        if input_values is None:
            input_values = partition(sum(output_values) + fee, len(inputs), rng)
        else:
            fee = sum(input_values) - sum(output_values)
        txid = f"tx_demo_{len(records) + 1:06d}"
        records.append(dict(zip(COLUMNS, [
            (START + timedelta(seconds=seconds)).isoformat(),
            f"192.0.2.{rng.randint(1, 254)}", f"198.51.100.{rng.randint(1, 254)}",
            rng.randint(49152, 65535), rng.choice([8333, 8333, 8333, 18333, 18444]),
            txid, json.dumps(inputs), json.dumps(outputs),
            json.dumps([btc(value) for value in input_values]),
            json.dumps([btc(value) for value in output_values]), btc(fee),
            rng.choice(["P2WPKH", "P2TR", "P2PKH", "P2SH"])
        ])))
        return txid

    wallets = [f"bc1q_demo_{index:04d}" for index in range(1, 601)]
    for index in range(rows - 37):
        n_in = rng.choice([1, 1, 1, 2, 3])
        n_out = rng.choice([1, 2, 2, 2, 3])
        selected = rng.sample(wallets, n_in + n_out)
        total = rng.randint(10_000, 200_000_000)
        # Spread ordinary observations across seven days rather than a short burst.
        seconds = index * 604800 // (rows - 37) + rng.randrange(60)
        transaction(seconds, selected[:n_in], selected[n_in:], partition(total, n_out, rng))

    peel_wallets = [f"wallet_peel_{index:02d}" for index in range(1, 7)]
    peel_recipients = [f"wallet_peel_recipient_demo_{index:02d}" for index in range(1, 6)]
    peel_txids = []
    balance = 890_000_000
    for index in range(5):
        transferred = 850_000_000 - index * 40_000_000
        fee = rng.randint(1000, 5000)
        peel_txids.append(transaction(86400 + index * 600, [peel_wallets[index]],
                                     [peel_wallets[index + 1], peel_recipients[index]],
                                     [transferred, balance - transferred - fee], [balance]))
        balance = transferred
    truth["scenarios"]["peeling_chain"] = {
        "wallets": peel_wallets + peel_recipients, "chain_wallets": peel_wallets,
        "txids": peel_txids, "transferred_btc": ["8.50000000", "8.10000000", "7.70000000", "7.30000000", "6.90000000"]}

    burst_wallet = "wallet_burst_demo"
    burst_targets = [f"wallet_burst_recipient_demo_{index:02d}" for index in range(1, 31)]
    burst_txids = [transaction(259200 + index * 2, [burst_wallet], [target],
                               [rng.randint(50_000, 5_000_000)])
                   for index, target in enumerate(burst_targets)]
    truth["scenarios"]["anomalous_burst"] = {
        "wallets": [burst_wallet] + burst_targets, "source_wallet": burst_wallet,
        "txids": burst_txids, "window_seconds": 58, "transaction_count": 30}

    path = ["seed_wallet_demo", "wallet_intermediate", "wallet_target"]
    path_txids = [transaction(432000, [path[0]], [path[1]], [125_000_000]),
                  transaction(433800, [path[1]], [path[2]], [124_997_000], [125_000_000])]
    truth["scenarios"]["seed_risk_path"] = {
        "wallets": path, "txids": path_txids, "seed_wallet": path[0], "target_wallet": path[-1]}
    records.sort(key=lambda row: (row["timestamp"], row["txid"]))
    validate_dataset(records, truth)
    return records, truth


def validate_dataset(records, truth):
    """Validate generated fields, balance, and evaluation entity membership."""
    if not records:
        raise ValueError("Dataset must not be empty")
    wallets, txids = set(), set()
    for row in records:
        if set(row) != set(COLUMNS) or any(row[key] in (None, "") for key in COLUMNS):
            raise ValueError("Missing required fields or values")
        datetime.fromisoformat(row["timestamp"])
        inputs, outputs = json.loads(row["input_addresses"]), json.loads(row["output_addresses"])
        amounts_in = [Decimal(value) for value in json.loads(row["input_amounts"])]
        amounts_out = [Decimal(value) for value in json.loads(row["output_amounts"])]
        if not inputs or not outputs or len(inputs) != len(amounts_in) or len(outputs) != len(amounts_out):
            raise ValueError("Address and amount lists must be nonempty and aligned")
        if any(value <= 0 for value in amounts_in + amounts_out) or Decimal(row["fee"]) <= 0:
            raise ValueError("Amounts and fees must be positive")
        if sum(amounts_in) != sum(amounts_out) + Decimal(row["fee"]):
            raise ValueError("Transaction amounts do not balance")
        if row["txid"] in txids:
            raise ValueError("Duplicate TXID")
        wallets.update(inputs + outputs)
        txids.add(row["txid"])
    for scenario in truth["scenarios"].values():
        if not set(scenario["wallets"]) <= wallets or not set(scenario["txids"]) <= txids:
            raise ValueError("Ground truth entities missing from generated records")


def save_dataset(records, truth, directory):
    """Write CSV observations and separate evaluation-only JSON labels."""
    validate_dataset(records, truth)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "demo_case.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    (directory / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")


def main():
    """Generate local demonstration data using simple optional CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.rows < 100:
        parser.error("--rows must be at least 100")
    records, truth = generate_dataset(args.rows, args.seed)
    save_dataset(records, truth, Path(__file__).resolve().parents[1] / "data")
    wallets = {wallet for row in records for column in ("input_addresses", "output_addresses")
               for wallet in json.loads(row[column])}
    print(f"Rows generated: {len(records)}")
    print(f"Unique TXIDs: {len({row['txid'] for row in records})}")
    print(f"Unique wallets: {len(wallets)}")
    print("Injected scenarios: " + ", ".join(truth["scenarios"]))


if __name__ == "__main__":
    main()
