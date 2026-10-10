# Tests for LINK: Links, images and orphans

Spec: [SPECIFICATIONS/LINK-links-images-orphans.md](../SPECIFICATIONS/LINK-links-images-orphans.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_links.py`, integration in `test_rules_integration.py`. Fixture journey `tests/fixtures/rules/links-journey/` (manual `guide` in Markdown with `entry: start.md`, manual `ops` in HTML without entry); small manuals built in `tmp_path`.

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_LINK_01_checks_registered_as_rule_checks` | AC-LINK-01 | unit | registry | tier rule; scopes manual/page/manual; categories as specified |
| `test_AC_LINK_02_empty_link_target_is_broken` | AC-LINK-02 | unit | `[empty one]()` | one finding 'empty target' |
| `test_AC_LINK_02_missing_file_in_html_page` | AC-LINK-02 | unit | `ops/index.html` `href="run.htm"` | one broken-link |
| `test_AC_LINK_02_missing_file_reported_as_major_broken_link` | AC-LINK-02 | unit | `guide/start.md` `[old page](old-page.md)` | one major broken-link, quote is the markup |
| `test_AC_LINK_03_existing_targets_not_reported` | AC-LINK-03 | unit | `setup.md`, `start.md`, `#` | no finding |
| `test_AC_LINK_04_broken_in_page_anchor_reported` | AC-LINK-04 | unit | `#details` (exists), `#nowhere` | one minor broken-anchor for #nowhere only |
| `test_AC_LINK_04_existing_in_page_anchor_html` | AC-LINK-04 | unit | HTML `#ops` (exists), `#missing-id` | finding for #missing-id only |
| `test_AC_LINK_05_cross_page_anchor_checked_against_target_page` | AC-LINK-05 | unit | `setup.md#installing`, `#configuring-it`, `#tuning` | one broken-anchor for #tuning |
| `test_AC_LINK_06_links_into_other_manual_resolve` | AC-LINK-06 | unit | guide ↔ ops links, `../ops/gone.html`, `run.html#failures` | existing resolve; missing file and anchor reported |
| `test_AC_LINK_06_single_manual_journey_still_checks_cross_manual_links` | AC-LINK-06 | unit | `load_journey(guide)` (one manual) | applies; `../ops/index.html` fine, `gone.html` reported |
| `test_AC_LINK_07_external_links_ignored` | AC-LINK-07 | unit | https, mailto, ftp, `//host` links | no finding |
| `test_AC_LINK_08_fix_suggests_similar_file_and_anchor` | AC-LINK-08 | unit | `run.htm`, `#Running`, `#failures` | 'Did you mean run.html', case hint, add id hint |
| `test_AC_LINK_09_several_broken_links_on_one_line_give_one_finding` | AC-LINK-09 | unit | two missing files on one line | one finding naming both |
| `test_AC_LINK_10_missing_image_file_reported` | AC-LINK-10 | unit | `![Diagram](img/diagram.png)`, `![Logo](img/ok.png)` | major 'Missing image' for diagram only |
| `test_AC_LINK_11_html_explicit_empty_alt_is_decorative` | AC-LINK-11 | unit | `<img src="pics/decorative.png" alt="">` | only the missing-file finding |
| `test_AC_LINK_11_image_without_alt_text_is_minor` | AC-LINK-11 | unit | `![](img/ok.png)` | one minor alt-text finding |
| `test_AC_LINK_12_missing_image_without_alt_gives_one_major_finding` | AC-LINK-12 | unit | `![](img/missing.png)` | one major finding, both problems |
| `test_AC_LINK_13_external_image_only_checked_for_alt` | AC-LINK-13 | unit | `<img src="https://…/remote.png">` | minor alt-text finding only |
| `test_AC_LINK_14_unlinked_page_reported_as_orphan` | AC-LINK-14 | unit | `guide/unused.md`, `ops/extra.html` | minor orphan-page at line 1 |
| `test_AC_LINK_15_entry_from_manual_yaml_wins_over_index` | AC-LINK-15 | unit | tmp manual, `entry: home.md`, unlinked `index.md` | only index.md reported |
| `test_AC_LINK_15_entry_pages_are_not_orphans` | AC-LINK-15 | unit | `start.md` (entry), `ops/index.html` (index) | not reported |
| `test_AC_LINK_16_links_from_other_manuals_count_but_self_links_do_not` | AC-LINK-16 | unit | `ops/run.html` linked from guide; `selfref.md` | run.html not orphan; selfref.md orphan |
| `test_AC_LINK_17_single_page_manual_has_no_orphans` | AC-LINK-17 | unit | tmp one-page manual | no finding |
| `test_AC_LINK_18_all_link_findings_verified_with_original_lines` | AC-LINK-18 | unit | fixture journey, all three checks | all verified, lines unchanged by verification |
| `test_AC_LINK_19_sample_review_link_findings_verified` | AC-LINK-19 | integration | `samples/shopflow/journey.yaml`, `ReviewService().review(..., ["rules"])` | no errors; findings; all rule findings verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
