import subprocess

from config.settings.common import BIN_ROOT, MEDIA_ROOT


def run(binary, args):
    """
    Run a binary, its pretty grim but for now does the trick
    """
    command = [f"{BIN_ROOT}/{binary}"] + args
    popen = subprocess.Popen(command, stdout=subprocess.PIPE)
    popen.wait()
    return popen.stdout.read()


def mp4fragment(video_name: str, output_name: str):
    """
    Calls Bento4 mp4fragment binary.
    """
    return run(
        "bento/tools/mp4fragment",
        [f"{MEDIA_ROOT}/{video_name}", f"{MEDIA_ROOT}/{output_name}"],
    )


def mp4dash(fragmented_video_name: str):
    """
    Calls Bento4 mp4dash binary.
    """
    run(
        "bento/tools/mp4dash",
        [
            "--encryption-key",
            "A16E402B9056E371F36D348AA62BB749:87237D20A19F58A740C05684E699B4AA,A16E402B9056E371F36D348AA62BB749:87237D20A19F58A740C05684E699B4AA",
            f"{MEDIA_ROOT}/{fragmented_video_name}",
        ],
    )
