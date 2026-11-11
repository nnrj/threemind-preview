"""Finish preregistered calibration/attribution and translate continuous histories."""

import torch
from bridge_ablation import main as bridge_main
from bridge_text import main as bridge_text_main
from language_analysis import evaluate
from stream_translations import translate
from weak_expression import main as weak_main
from weak_validation import main as validate_main


def main():
    torch.set_num_threads(2)
    weak_main()
    validate_main()
    for seed in (11, 37, 53):
        for route in ("stream-sparse", "text"):
            evaluate(route, seed, "weak")
    bridge_main()
    bridge_text_main()
    for seed in (11, 37, 53):
        for route in ("stream-sparse", "text"):
            for variant in ("base", "weak"):
                translate(route, seed, variant)


if __name__ == "__main__":
    main()
