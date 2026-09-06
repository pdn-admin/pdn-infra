#!/usr/bin/env python3
"""
Compress old WAV audio files to MP3 for users older than 1 month.

Saves ~60-70% disk space by converting WAV recordings to MP3.
Only processes files older than 30 days to avoid touching active users.

Usage:
    # Dry run (show what would be compressed):
    python tools/compress_old_audio.py --dry-run

    # Actually compress:
    python tools/compress_old_audio.py

    # Custom age threshold (e.g., 7 days):
    python tools/compress_old_audio.py --days 7

    # Custom directory:
    python tools/compress_old_audio.py --dir /pdn/saved_results

Requirements:
    pip install pydub
    # Also needs ffmpeg installed:
    # macOS: brew install ffmpeg
    # Ubuntu: apt-get install ffmpeg
    # Render: add to requirements or use apt in build
"""

import os
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta

try:
    from pydub import AudioSegment
    USE_PYDUB = True
except ImportError:
    USE_PYDUB = False
    import subprocess
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: Neither pydub nor ffmpeg found.")
        print("Install one of: pip install pydub / brew install ffmpeg")
        sys.exit(1)


def get_file_age_days(file_path: Path) -> float:
    """Get file age in days based on modification time."""
    mtime = file_path.stat().st_mtime
    age_seconds = time.time() - mtime
    return age_seconds / 86400


def format_size(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


def compress_wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "64k") -> bool:
    """
    Convert WAV file to MP3.
    
    Args:
        wav_path: Source WAV file
        mp3_path: Destination MP3 file
        bitrate: MP3 bitrate (64k is good for voice, saves ~50-70%)
    
    Returns:
        True if successful
    """
    try:
        if USE_PYDUB:
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3", bitrate=bitrate)
        else:
            result = subprocess.run(
                ['ffmpeg', '-i', str(wav_path), '-b:a', bitrate, '-y', str(mp3_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"  ffmpeg error: {result.stderr[:100]}")
                return False
        return mp3_path.exists()
    except Exception as e:
        print(f"  ERROR compressing {wav_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Compress old WAV audio files to MP3")
    parser.add_argument("--dir", default="saved_results",
                        help="Directory containing user folders (default: saved_results)")
    parser.add_argument("--days", type=int, default=30,
                        help="Only compress files older than N days (default: 30)")
    parser.add_argument("--bitrate", default="64k",
                        help="MP3 bitrate (default: 64k, good for voice)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without actually compressing")
    parser.add_argument("--keep-wav", action="store_true",
                        help="Keep original WAV files after compression (default: delete)")
    args = parser.parse_args()

    base_dir = Path(args.dir)
    if not base_dir.exists():
        # Try relative to project root
        base_dir = Path(__file__).parent.parent / args.dir
        if not base_dir.exists():
            print(f"ERROR: Directory not found: {args.dir}")
            sys.exit(1)

    print(f"{'=' * 60}")
    print(f"  Audio Compression Tool — WAV → MP3")
    print(f"{'=' * 60}")
    print(f"  Directory:  {base_dir}")
    print(f"  Threshold:  Files older than {args.days} days")
    print(f"  Bitrate:    {args.bitrate}")
    print(f"  Dry run:    {'YES' if args.dry_run else 'NO'}")
    print(f"  Keep WAV:   {'YES' if args.keep_wav else 'NO (delete after compress)'}")
    print(f"{'=' * 60}\n")

    # Find all WAV files older than threshold
    cutoff_date = datetime.now() - timedelta(days=args.days)
    wav_files = []
    
    for user_dir in base_dir.iterdir():
        if not user_dir.is_dir():
            continue
        for wav_file in user_dir.glob("*.wav"):
            age_days = get_file_age_days(wav_file)
            if age_days >= args.days:
                wav_files.append((wav_file, age_days))

    if not wav_files:
        print(f"✓ No WAV files older than {args.days} days found. Nothing to compress.")
        return

    # Sort by age (oldest first)
    wav_files.sort(key=lambda x: -x[1])

    # Calculate totals
    total_wav_size = sum(f.stat().st_size for f, _ in wav_files)
    
    print(f"Found {len(wav_files)} WAV files to compress")
    print(f"Total WAV size: {format_size(total_wav_size)}")
    print(f"Estimated MP3 size: ~{format_size(int(total_wav_size * 0.15))} (at {args.bitrate})")
    print(f"Estimated savings: ~{format_size(int(total_wav_size * 0.85))}")
    print()

    if args.dry_run:
        print("DRY RUN — listing files that would be compressed:\n")
        for wav_file, age_days in wav_files:
            size = format_size(wav_file.stat().st_size)
            user = wav_file.parent.name
            print(f"  [{int(age_days)}d old] {user}/{wav_file.name} ({size})")
        print(f"\n{'=' * 60}")
        print(f"  Would compress {len(wav_files)} files, saving ~{format_size(int(total_wav_size * 0.85))}")
        print(f"  Run without --dry-run to execute.")
        print(f"{'=' * 60}")
        return

    # Actually compress
    success = 0
    failed = 0
    bytes_saved = 0

    for i, (wav_file, age_days) in enumerate(wav_files, 1):
        mp3_file = wav_file.with_suffix('.mp3')
        wav_size = wav_file.stat().st_size
        user = wav_file.parent.name

        print(f"  [{i}/{len(wav_files)}] {user}/{wav_file.name} ({format_size(wav_size)})...", end=" ")

        if compress_wav_to_mp3(wav_file, mp3_file, args.bitrate):
            mp3_size = mp3_file.stat().st_size
            saved = wav_size - mp3_size
            bytes_saved += saved
            
            if not args.keep_wav:
                wav_file.unlink()
            
            success += 1
            print(f"✓ {format_size(mp3_size)} (saved {format_size(saved)})")
        else:
            failed += 1
            print("✗ FAILED")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  DONE")
    print(f"  Compressed: {success}/{len(wav_files)} files")
    print(f"  Failed:     {failed}")
    print(f"  Space saved: {format_size(bytes_saved)}")
    if not args.keep_wav:
        print(f"  Original WAVs deleted: {success}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
