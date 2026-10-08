from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from brrs.scenario_loader import load_scenario
from brrs.core.model import BankRobberyModel


def run_experiment_batch(scenarios: list[str], runs_per_scenario: int = 15, output_dir: str = "results") -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    records = []

    print(f"[*] Running batch evaluation: {len(scenarios)} scenarios x {runs_per_scenario} runs...")

    for sc_name in scenarios:
        cfg = load_scenario(sc_name)
        for r_idx in range(runs_per_scenario):
            seed = (cfg.seed or 100) + r_idx * 7
            model = BankRobberyModel(cfg, seed=seed)

            for _ in range(cfg.sim.max_ticks):
                model.step()
                if model.is_finished:
                    break

            summary = model.metrics.to_summary_dict()
            summary["scenario"] = sc_name
            summary["run_index"] = r_idx
            summary["seed"] = seed
            records.append(summary)

    df = pd.DataFrame(records)
    csv_file = out_path / "batch_results.csv"
    df.to_csv(csv_file, index=False)
    print(f"[+] Saved detailed run data to: {csv_file}")

    # Aggregated Summary
    grouped = df.groupby("scenario").agg(
        success_rate=("interception_success", "mean"),
        avg_detection_time=("detection_time_ticks", "mean"),
        avg_response_time=("response_time_ticks", lambda x: x[x >= 0].mean() if len(x[x >= 0]) else 0),
        avg_police_distance=("total_police_travel_distance_m", "mean"),
        avg_replans=("total_route_replannings", "mean"),
    ).reset_index()

    summary_file = out_path / "scenario_summary.csv"
    grouped.to_csv(summary_file, index=False)
    print(f"[+] Saved aggregated summary to: {summary_file}")

    # Plotting Comparative Charts
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Multi-Agent Bank Robbery Response: Scenario Comparative Analysis", fontsize=16)

    # 1. Success Rate
    axes[0, 0].bar(grouped["scenario"], grouped["success_rate"] * 100, color="#388bfd")
    axes[0, 0].set_title("Interception Success Rate (%)")
    axes[0, 0].set_ylabel("Success Rate (%)")
    axes[0, 0].set_ylim(0, 105)
    axes[0, 0].tick_params(axis='x', rotation=25)

    # 2. Avg Replannings
    axes[0, 1].bar(grouped["scenario"], grouped["avg_replans"], color="#e3b341")
    axes[0, 1].set_title("Average Tactical Route Replannings")
    axes[0, 1].set_ylabel("Replans Count")
    axes[0, 1].tick_params(axis='x', rotation=25)

    # 3. Detection & Response Time
    x = range(len(grouped))
    width = 0.35
    axes[1, 0].bar([i - width/2 for i in x], grouped["avg_detection_time"], width, label="Detection Time", color="#ff7b72")
    axes[1, 0].bar([i + width/2 for i in x], grouped["avg_response_time"], width, label="Response Time", color="#a371f7")
    axes[1, 0].set_title("Average Temporal Metrics (Ticks)")
    axes[1, 0].set_xticks(list(x))
    axes[1, 0].set_xticklabels(grouped["scenario"], rotation=25)
    axes[1, 0].legend()

    # 4. Police Travel Distance
    axes[1, 1].bar(grouped["scenario"], grouped["avg_police_distance"], color="#2ea043")
    axes[1, 1].set_title("Average Dispatched Police Travel Distance (m)")
    axes[1, 1].set_ylabel("Distance (m)")
    axes[1, 1].tick_params(axis='x', rotation=25)

    plt.tight_layout()
    chart_file = out_path / "experiment_analysis.png"
    plt.savefig(chart_file, dpi=300)
    plt.close()
    print(f"[+] Saved comparison charts to: {chart_file}")


def main():
    parser = argparse.ArgumentParser(description="Run headless experiments across MAS scenarios")
    parser.add_argument("--runs", type=int, default=15, help="Number of repetitions per scenario")
    parser.add_argument("--output", type=str, default="results", help="Target output directory")
    args = parser.parse_args()

    scenarios = [
        "baseline",
        "rush_hour",
        "blind_spots",
        "outnumbered",
        "fast_getaway",
        "large_city",
    ]
    run_experiment_batch(scenarios, runs_per_scenario=args.runs, output_dir=args.output)


if __name__ == "__main__":
    main()
