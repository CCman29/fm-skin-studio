"""The screens people actually open in FM27, under plain names, and which settings each one uses.

FM27 ships ~1,800 grid layouts (every screen x breakpoint x variant). The editor offers the main ones at the
Large breakpoint (the one the game writes for a normal desktop window). Settings are found by walking every
element of the screen's panels and matching the game's style rules against their classes.
"""

from __future__ import annotations

import re

# Screen-only backdrop hooks: screen roots have no names, these structures are unique to each screen's file.
# Training confirmed in game (2026-10-31). Club failed as a direct-child chain (the game wraps the frame at run time),
# so club/recruit use descendant/looser chains; both await an in-game check.
BACKDROP_HOOKS = {
    "training": ".calendar-button-group > SISafeAreaElement#Overview",
    "recruit": ".align-self-auto > #Card-frame > *",
    "club": "#TeamAndPersonRemapper #Card-frame > *",
}

# (label, group, layout, backdrop key, what the screen is)
SCREENS = [
    ("Home (Portal)", "Home", "Portal-Large", "home", "The inbox and dashboard you land on every day."),
    ("Team Overview (Squad)", "Squad", "SquadComposition-Large", "home", "First-team overview with atmosphere, tactics and training tiles."),
    ("Squad Atmosphere", "Squad", "SquadAtmosphereCardComposition-Large", "home", "Dressing-room mood, hierarchy and happiness."),
    ("Youth Setup", "Squad", "SquadYouthSetupReportOverviewGridComposition-Large", "home", "Youth intake and development overview."),
    ("Player Profile", "Players", "PlayerReportOverviewComposition-Large", "home", "A player's overview page."),
    ("Player Performance", "Players", "PlayerReportPerformance-Large", "home", "A player's stats and form."),
    ("Player Personal", "Players", "PlayerReportPersonal-Large", "home", "Personality, relationships and history."),
    ("Contract Negotiation", "Players", "ContractNegotiationGridComposition_Large", "home", "Agreeing terms with a player."),
    ("Tactics: Team Instructions", "Tactics", "TacticalPlannerTeamInstructionsTabComposition-Large", "home", "Team instructions tab of the tactics screen."),
    ("Tactics: Set Pieces", "Tactics", "TeamReportSetPieceTabGridComposition-Large", "home", "Set-piece takers and routines."),
    ("Training Overview", "Training", "TrainingOverviewGridComposition-Large", "training", "Weekly schedule, tactical effectiveness and staff."),
    ("Coaching Team", "Training", "CoachingTeamTabGridComposition-Large", "training", "Coaches and their workloads."),
    ("Medical Centre", "Training", "MedicalCentreCurrentInjuriesReportGridComposition-Large", "home", "Current injuries and treatment."),
    ("Medical Team", "Training", "MedicalTeamTabGridComposition-Large", "home", "Medical staff and their workloads."),
    ("Recruitment Hub", "Recruitment", "RecruitmentComposition-Large", "recruit", "Transfer room, window, budgets and agent offers."),
    ("Player Database (bottom tiles)", "Recruitment", "PlayerSearchReportGridCompositionBottomBarLarge", "recruit",
     "The tiles under the player search table."),
    ("Transfer Budgets", "Recruitment", "RecruitmentTransferBudgetsCardGridComposition-Large", "recruit", "Transfer and wage budget breakdown."),
    ("Scouting Report", "Recruitment", "ScoutingReportCardGridComposition-Large", "recruit", "A scout's report on a player."),
    ("Transfer Offer", "Recruitment", "TransferOfferToolGridComposition-Large", "recruit", "Making an offer for a player."),
    ("Club Overview", "Club", "ClubComposition-Large", "club", "Club info, profile, facilities and transfer history."),
    ("Club Finances", "Club", "ClubFinancesCardGridComposition-Large", "club", "Income, spending and budgets."),
    ("Club Board", "Club", "ClubBoardCardGridComposition-Large", "club", "Board confidence and requests."),
    ("Club Vision", "Club", "ClubVisionCardGridComposition-Large", "club", "The board's long-term plan."),
    ("Supporters", "Club", "ClubSupportersCardGridComposition-Large", "club", "Fan confidence and expectations."),
    ("Staff Overview", "Club", "OverviewTabGridComposition-Large", "home", "Coaching, recruitment and medical staff."),
    ("Team Report", "Data Hub", "TeamReportOverviewTabGridComposition-Large", "home", "Team report overview."),
    ("Data Hub Key Findings", "Data Hub", "DataHubKeyFindingsGridComposition-Large", "home", "The analyst's headline findings."),
    ("Opposition Report", "Matches", "OppositionReportCardGridComposition_ReportAvailable-Large", "home", "Scouting the next opponent."),
    ("Match Preparation", "Matches", "MatchPreparationCardGridComposition-Large", "home", "Pre-match briefing."),
    ("Match Day", "Matches", "MatchExperienceGridComposition-Large", "home", "The live match screen with its side panels."),
    ("Half-Time Report", "Matches", "HalfTimeTeamReportGridComposition-Large", "home", "Half-time team talk and stats."),
    ("Full-Time Report", "Matches", "FullTimeTeamReportGridComposition-Large", "home", "Post-match stats and ratings."),
    ("Competitions Overview", "Competitions", "CompetitionsOverview5CompsGridComposition-Large", "home", "All your competitions at a glance."),
    ("Competition Stages", "Competitions", "CompetitionStagesCardStagesGridComposition-Large", "home", "League table and stage view."),
    ("Main Menu", "Menus", "MainMenuHasSaveComposition-Large", "home", "The start screen with a save to continue."),
]

_LAST = re.compile(r"\s*>\s*|\s+")


def catalog(available: set[str]) -> list[dict]:
    return [{"label": label, "group": group, "layout": layout, "backdrop": backdrop, "about": about,
             "ownBackdrop": backdrop in BACKDROP_HOOKS}
            for label, group, layout, backdrop, about in SCREENS if layout in available]


def classes_in(tree: dict | None, out: set[str] | None = None) -> set[str]:
    out = set() if out is None else out
    if tree:
        out.update(tree.get("c") or [])
        for ch in tree.get("ch") or []:
            classes_in(ch, out)
    return out


def tokens_for_classes(by_token: dict[str, list], present: set[str]) -> dict[str, int]:
    """Tokens whose rules target elements on the screen: every class of a rule's last selector part is present.
    Returns token -> number of rules on this screen using it."""
    hits: dict[str, int] = {}
    for token, rules in by_token.items():
        for selector, _prop in rules:
            for part in selector.split(","):
                last = _LAST.split(part.strip())[-1]
                classes = re.findall(r"\.([^\s.#:>*]+)", last)
                if classes and all(c in present for c in classes):
                    hits[token] = hits.get(token, 0) + 1
                    break
    return hits
