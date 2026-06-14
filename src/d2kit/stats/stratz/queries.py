"""GraphQL query strings, validated against the live STRATZ API in scripts/."""

# id -> name resolution for items and heroes.
CONSTANTS = """
query Constants {
  constants {
    items { id shortName }
    heroes { id shortName displayName }
  }
}
"""

# Lightweight recent-match list for the match picker (no heavy stats).
PLAYER_RECENT_MATCHES = """
query PlayerRecentMatches($id: Long!, $take: Int!) {
  player(steamAccountId: $id) {
    matches(request: { isParsed: true, take: $take }) {
      id
      startDateTime
      gameMode
      players(steamAccountId: $id) { heroId isVictory }
    }
  }
}
"""

# Full per-match timings for one account on one hero, in a single call: stats are
# nested inside the matches list and filtered to the account. Used for both the
# personal mean and (per pro account) the pro-pub benchmark. lobbyTypeIds:[7]=RANKED.
PLAYER_HERO_MATCHES = """
query PlayerHeroMatches($id: Long!, $hero: Short!, $take: Int!) {
  player(steamAccountId: $id) {
    steamAccount { isAnonymous }
    matches(request: { heroIds: [$hero], lobbyTypeIds: [7], isParsed: true, take: $take }) {
      id
      players(steamAccountId: $id) {
        heroId
        stats {
          itemPurchases { itemId time }
          networthPerMinute
          lastHitsPerMinute
        }
        playbackData { abilityLearnEvents { time } }
      }
    }
  }
}
"""

# Timings for one account in one specific match (the match under analysis).
MATCH_PLAYER_TIMINGS = """
query MatchPlayerTimings($id: Long!, $account: Long!) {
  match(id: $id) {
    id
    players(steamAccountId: $account) {
      heroId
      stats {
        itemPurchases { itemId time }
        networthPerMinute
        lastHitsPerMinute
      }
      playbackData { abilityLearnEvents { time } }
    }
  }
}
"""
