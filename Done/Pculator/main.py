#!/usr/bin/env python3
import os
import argparse
from Sandbox.horizon.PFE_Calculator.models.pfe_engine import PFEEngine


def main(template_path: str):
    """
    Entry point for PFE processing.

    - If the template does not exist, it will be created and program will exit.
    - Otherwise, it reads the template, computes PFE, and writes results.
    """
    engine = PFEEngine(template_path=template_path)
    engine.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run PFE calculation: generate template or process input and export results.'
    )
    parser.add_argument(
        '--template', '-t',
        default='PFE_template.xlsx',
        help='Path to PFE template file (default: PFE_template.xlsx)'
    )
    args = parser.parse_args()

    # 调用主逻辑
    main(template_path=args.template)
