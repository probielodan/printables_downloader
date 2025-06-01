# Printables Downloader

Download 3D model files from [Printables.com](https://printables.com) easily via command line.

## Features

- Supports all file types (configurable)
- Persistent HTTP session for faster downloads
- Retries and graceful error handling
- Dry run mode and verbose output

## Installation

```bash
pip install printables_downloader
```

## Usage

```bash
printables-downloader <model-url> [-o output_dir] [-e .3mf .stl] [--dry] [-v]
```

## Example

```bash
printables-downloader https://printables.com/model/1234567 --ext .3mf .stl -o downloads -v
```

## License

MIT License © Praise Obielodan
