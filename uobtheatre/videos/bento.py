import subprocess

from config.settings.common import BIN_ROOT, MEDIA_ROOT


"""
Bento is a powerful tool which we use to covert mp4s into encrypted mp4dash
files. Currently we use the binaries from the bento sdk directly. This is a
pretty horrible solution and hopefully we can swap these out for the c++/python
libraries in the future. For now though we will have to make sure we install
the binaries before working on the bento side of things.

TODO:
Find a way to store the bento stuff (probably the drive) with install
instructions. For now the aim is to make bento stuff a seperate thing that most
people wont care about. If someone want to work on the bento stuff it will
require a couple of extra steps but then they should be good to go as well.

NOTES:
mp4fragment - can probably use Mp4Fragment.cpp directly, gonna need to do some
reading
https://realpython.com/python-bindings-overview/#python-bindings-overview 🥳

mp4dash - https://github.com/axiomatic-systems/Bento4/issues/274
mp4dash is written in python and depends on the c++ binaries (I think)
"""


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
            "-o",
            f"{MEDIA_ROOT}/{fragmented_video_name}_output",
        ],
    )
