from uobtheatre.videos.bento import mp4dash, mp4fragment


def test_mp4fragment():
    print(mp4fragment("input-video.mp4", "video-fragmented.mp4"))


def test_mp4dash():
    print(mp4dash("video-fragmented.mp4"))
