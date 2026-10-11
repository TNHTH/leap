# Branch audit 2026-10-12

Canonical branch is main. The pre-audit snapshot is tag `stable-2026-10-12` at `cb5f5ae2e8ea66a6b93da02846a0c5140e344b21`.

`work` has no path or blob that this main lacked. It is not a second product line.

`chore/top-level-root-migration` still contains `archives/imported/`, including generated manuals, firmware binaries, and executables. Later commits removed that dump before the verified snapshot. Those files are not restored to the work tree. Tag `archive-imported-2026-04-11` keeps that tree reachable.
