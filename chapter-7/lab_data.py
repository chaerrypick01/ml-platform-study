"""Download, validate and split COCO128 into reproducible disjoint subsets."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import urllib.request
import zipfile

import yaml

URL = 'https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as stream:
        for member in stream.infolist():
            if not (destination / member.filename).resolve().is_relative_to(destination):
                raise ValueError(f'Unsafe archive member: {member.filename}')
        stream.extractall(destination)


def configure(root):
    root = Path(root).resolve()
    config = yaml.safe_load((root / 'data.yaml').read_text())
    config['path'] = str(root)
    (root / 'data.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    return root / 'data.yaml'


def prepare(output, seed=42):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f'Output must be empty: {output}')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'source.zip'
    urllib.request.urlretrieve(URL, archive)
    source_sha = digest(archive)
    unpack(archive, output / 'source')
    source = output / 'source/coco128'
    images = sorted((source / 'images/train2017').glob('*.jpg'))
    if len(images) != 128:
        raise ValueError(f'Expected 128 images, got {len(images)}')
    random.Random(seed).shuffle(images)
    groups = {'train': images[:96], 'val': images[96:112], 'test': images[112:]}
    manifest = {'url': URL, 'archive_sha256': source_sha, 'seed': seed, 'splits': {}}
    for split, paths in groups.items():
        (output / f'images/{split}').mkdir(parents=True)
        (output / f'labels/{split}').mkdir(parents=True)
        records = []
        for image in paths:
            label = source / 'labels/train2017' / f'{image.stem}.txt'
            target = output / f'labels/{split}/{image.stem}.txt'
            target.write_text(label.read_text() if label.exists() else '')
            for line in target.read_text().splitlines():
                values = [float(v) for v in line.split()]
                if (len(values) != 5 or not values[0].is_integer()
                        or not 0 <= values[0] < 80 or not all(0 <= v <= 1 for v in values[1:])):
                    raise ValueError(f'Invalid YOLO label: {label}: {line}')
            shutil.copy2(image, output / f'images/{split}/{image.name}')
            records.append({'image': image.name, 'image_sha256': digest(image),
                            'label_sha256': digest(target)})
        manifest['splits'][split] = records
    hashes = [{r['image_sha256'] for r in records} for records in manifest['splits'].values()]
    if any(hashes[i] & hashes[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError('Duplicate image content across splits')
    config = yaml.safe_load((Path(__file__).with_name('coco_names.yaml')).read_text())
    config = {'path': str(output), 'train': 'images/train', 'val': 'images/val',
              'test': 'images/test', 'names': config['names']}
    (output / 'data.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    shutil.rmtree(output / 'source')
    archive.unlink()
    print(json.dumps({'counts': {k: len(v) for k, v in groups.items()},
                      'archive_sha256': source_sha, 'overlap': 0}), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    prepare(args.output, args.seed)
