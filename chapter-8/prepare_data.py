"""Prepare chapter 8 inputs using the chapter 7 data preparation function."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chapter-7'))
from lab_data import prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    prepare(args.output, args.seed)
