"""GraphQL query strings, validated against the live STRATZ API in scripts/."""

# id -> name resolution for items and heroes.
CONSTANTS = """
query Constants {
  constants {
    items { id shortName stat { cost } }
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
      players(steamAccountId: $id) { heroId isVictory position }
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
      durationSeconds
      players(steamAccountId: $id) {
        heroId
        position
        isVictory
        stats {
          itemPurchases { itemId time }
          networthPerMinute
          lastHitsPerMinute
          heroDamagePerMinute
          towerDamagePerMinute
        }
        playbackData { abilityLearnEvents { time } }
      }
    }
  }
}
"""

# Shared per-match-player timing selection, reused by the batched cohort query
# below so the (long) stats block isn't repeated once per aliased account.
_TIMINGS_FRAGMENT = """
fragment Timings on MatchPlayerType {
  heroId
  position
  isVictory
  stats {
    itemPurchases { itemId time }
    networthPerMinute
    lastHitsPerMinute
    heroDamagePerMinute
    towerDamagePerMinute
  }
  playbackData { abilityLearnEvents { time } }
}
"""


def build_cohort_query(account_ids: list[int]) -> str:
    """One aliased query fetching recent hero matches for several accounts at once.

    GraphQL field aliasing batches what used to be one HTTP call per pro account
    into a single request. ``$hero``/``$take`` stay variables, but account ids
    can't be GraphQL variables when used as aliases, so they're inlined — each is
    cast to ``int`` first, which both validates them and prevents injection.

    Each alias also pulls ``steamAccount { id name }`` (for the "who was compared"
    read-out) and ``durationSeconds`` (for duration-gated divergence).

    Keep the batch small: STRATZ caps query complexity at 300k (~10 full-stat
    accounts per request); see ``benchmark.fetch_pro_cohort``.
    """
    aliases = "\n".join(
        f"  p{i}: player(steamAccountId: {int(aid)}) {{"
        f" steamAccount {{ id name }}"
        f" matches(request: {{ heroIds: [$hero], lobbyTypeIds: [7], isParsed: true, take: $take }})"
        f" {{ id durationSeconds players(steamAccountId: {int(aid)}) {{ ...Timings }} }} }}"
        for i, aid in enumerate(account_ids)
    )
    return f"{_TIMINGS_FRAGMENT}\nquery Cohort($hero: Short!, $take: Int!) {{\n{aliases}\n}}"


# Timings for one account in one specific match (the match under analysis).
MATCH_PLAYER_TIMINGS = """
query MatchPlayerTimings($id: Long!, $account: Long!) {
  match(id: $id) {
    id
    durationSeconds
    players(steamAccountId: $account) {
      heroId
      position
      isVictory
      stats {
        itemPurchases { itemId time }
        networthPerMinute
        lastHitsPerMinute
        heroDamagePerMinute
        towerDamagePerMinute
      }
      playbackData { abilityLearnEvents { time } }
    }
  }
}
"""
