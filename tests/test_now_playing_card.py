from app.now_playing_card import NowPlayingCard


def test_now_playing_card_builds_expected_metadata():
    card = NowPlayingCard(
        title='Midnight Avenue',
        artist='Nova Blue',
        album='Signals',
        duration='3:42',
    )

    assert card.title == 'Midnight Avenue'
    assert card.artist == 'Nova Blue'
    assert card.album == 'Signals'
    assert card.duration == '3:42'

    snapshot = card.snapshot()
    assert snapshot['title'] == 'Midnight Avenue'
    assert snapshot['artist'] == 'Nova Blue'
