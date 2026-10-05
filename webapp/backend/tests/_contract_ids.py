"""Mechanical index of contracts exercised by each rewritten test area."""

B_SET_CONTRACT_IDS = tuple(f"B-SET-{number:03d}" for number in range(1, 33))
B_NEW_GAME_RULES_IDS = ("B-NEW-001", "B-NEW-002")

# This pilot owns app/settings/adapter and game-rule behavior as a single area.
B_SET_AREA_IDS = B_SET_CONTRACT_IDS + B_NEW_GAME_RULES_IDS
CONTRACT_IDS_BY_AREA = {"B-SET": B_SET_CONTRACT_IDS, "B-NEW-GAME": B_NEW_GAME_RULES_IDS}
