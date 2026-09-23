import argparse
import csv
from pathlib import Path


VARIANT_FOLDERS = {
    "V1": "v1_all_topics",
    "V2": "v2_single_topic",
    "V3": "v3_title_only",
    "V6": "v6_all_topics_abstract_natural_language",
}

EXPERIMENTS = {
    "random_100": {
        "openai": Path("output/full_metadata_model_comparison"),
        "gemini": Path("output/gemini_websearch"),
    },
    "top10": {
        "openai": Path("output/top10_visibility/requested_openai"),
        "gemini": Path("output/top10_visibility/requested_gemini"),
    },
}


def export_prompts(destination: Path) -> None:
    for dataset_set, providers in EXPERIMENTS.items():
        dataset_dir = destination / dataset_set
        dataset_dir.mkdir(parents=True, exist_ok=True)

        for variant, variant_folder in VARIANT_FOLDERS.items():
            prompts_by_provider = {}
            for provider, experiment_root in providers.items():
                source = experiment_root / variant_folder / "queries.csv"
                prompts = set()
                if source.exists():
                    with source.open("r", encoding="utf-8-sig", newline="") as handle:
                        for row in csv.DictReader(handle, delimiter=";"):
                            prompt = (row.get("full_prompt_web_search") or "").strip()
                            if prompt:
                                prompts.add(prompt)
                prompts_by_provider[provider] = prompts

            if variant != "V6" and len(set(map(frozenset, prompts_by_provider.values()))) != 1:
                raise ValueError(
                    f"{dataset_set}/{variant} prompts differ between providers"
                )

            exports = (
                prompts_by_provider.items()
                if variant == "V6"
                else [("shared", prompts_by_provider["openai"])]
            )
            for provider_label, prompts in exports:
                suffix = f"_{provider_label}" if variant == "V6" else ""
                path = dataset_dir / f"{variant.lower()}_prompts{suffix}.csv"
                with path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["prompt"], delimiter=";")
                    writer.writeheader()
                    writer.writerows({"prompt": prompt} for prompt in sorted(prompts))
                print(
                    f"{dataset_set}/{provider_label}/{variant}: "
                    f"{len(prompts)} prompts -> {path}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export unique generated web-search prompts by query variant."
    )
    parser.add_argument("--destination", default="reports/generated_prompts")
    args = parser.parse_args()
    export_prompts(Path(args.destination))


if __name__ == "__main__":
    main()
