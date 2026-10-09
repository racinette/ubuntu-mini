# Gamepad chord typing V1

V1 provides English letters, digits, space and US keyboard punctuation through ordinary key presses. Frequent characters use easier chords; mirrored punctuation and ordered digit groups make the less frequent chords easier to remember. It uses the existing virtual keyboard, with no custom Sway keymap, typing mode or onscreen keyboard.

The encoded layout is the `chords` object in [setup/desktop/gamepad.json](../setup/desktop/gamepad.json). Setup installs it with the navigation profile. These character labels assume the active keyboard layout is US English. Selecting another keyboard layout changes the characters produced by the same key codes.

## Release behavior

Press the controls in any order, keeping them overlapping. Release all D-pad and face inputs to emit one key. Releasing one part first does not emit a character or its single action. Triggers remain held modifiers; their state when the gesture finishes determines Shift/Ctrl behavior. Keep Shift held until the chord has finished to type uppercase or shifted punctuation.

A single D-pad direction still emits its arrow; A/B/X/Y still emit Enter/Escape/Backspace/Tab. These inputs now all wait for release. Holding a D-pad direction no longer repeats; sticks retain their existing navigation and repeat behavior. Invalid and unassigned combinations emit nothing and consume their single actions. Once release begins, pressing another D-pad direction or face button cancels the gesture; finish releasing before starting the next character.

Tap L3 before a gesture to add [one-shot Super](gamepad-controls.md#one-shot-super). It applies to one emitted key and then releases automatically. Shift/Ctrl trigger holds still combine with it; invalid/unassigned gestures leave Super armed, and a second L3 tap cancels it.

## Convenience tiers

| Tier | Combination | Available | Assigned |
| --- | --- | ---: | ---: |
| 1 | One D-pad direction and one face button | 16 | 16 |
| 2 | Two adjacent D-pad directions | 4 | 4 |
| 3 | Two adjacent face buttons | 4 | 4 |
| 4 | Two adjacent D-pad directions and one face button | 16 | 16 |
| 5 | One D-pad direction and two adjacent face buttons | 16 | 8 |
| 6 | Adjacent pairs on both sides | 16 | 0 |
| Total | | 72 | 48 |

The eight single inputs are navigation/editing controls and are excluded from these symbol slots. Opposite pairs are excluded. Face buttons form the diamond X left, Y up, B right, A down; adjacent pairs are X+Y, Y+B, A+B and X+A.

## Tier 1 letters and space

Tier 1 contains space and the 15 most frequent English letters in [Peter Norvig's Google Books analysis](https://www.norvig.com/mayzner.html): e, t, a, o, i, n, s, r, h, l, d, c, u, m, f. These account for about 89% of that sample's letters; this percentage excludes whitespace and punctuation. `Down+A` is space: the bottom direction with the bottom face button. Frequency chooses the set of letters, rather than ranking individual gestures within a tier.

| D-pad | X | Y | B | A |
| --- | --- | --- | --- | --- |
| Up | t | e | r | o |
| Left | a | s | i | n |
| Right | l | d | c | f |
| Down | m | h | u | Space |

## Tiers 2 and 3

| Tier | Chord | Normal | Shift |
| --- | --- | --- | --- |
| 2 | Up+Left | 9 | ( |
| 2 | Up+Right | 0 | ) |
| 2 | Down+Left | - | _ |
| 2 | Down+Right | Single quote | Double quote |
| 3 | X+Y | , | < |
| 3 | Y+B | . | > |
| 3 | X+A | ; | : |
| 3 | A+B | = | + |

Opening/closing parentheses occupy the left/right upper D-pad diagonals. Comma/period and less-than/greater-than occupy the upper left/right face pairs. These tiers prioritize common programming punctuation while keeping related symbols together.

## Tier 4 brackets, letters and digits

Each cell combines its D-pad pair with the named face button. Brackets/braces mirror both the D-pad and face side: Up+Left+X opens, Up+Right+B closes. Digits 1–6 follow the X, Y, B, A order across the lower diagonals.

| D-pad pair | X | Y | B | A |
| --- | --- | --- | --- | --- |
| Up+Left | [ / { with Shift | p | g | w |
| Up+Right | y | b | ] / } with Shift | v |
| Down+Left | 1 | 2 | 3 | 4 |
| Down+Right | 5 | 6 | k | x |

Shift capitalizes letters and gives digits 1–6 their ordinary US keyboard symbols: `! @ # $ % ^`.

## Tier 5 remaining characters

| Tier | Chord | Normal | Shift |
| --- | --- | --- | --- |
| 5 | Left+X+Y | 7 | & |
| 5 | Right+Y+B | 8 | * |
| 5 | Up+X+Y | q | Q |
| 5 | Up+Y+B | j | J |
| 5 | Down+X+A | Backtick | ~ |
| 5 | Down+A+B | Backslash | Vertical bar |
| 5 | Left+X+A | z | Z |
| 5 | Right+A+B | / | ? |

Parentheses use Shift with 9/0, and braces use Shift with brackets, as on a US keyboard. Quotes, slash, comma/period and other punctuation also keep their normal keyboard Shift behavior in V1.

All 95 printable ASCII characters are reachable through the 48 key slots and Shift. Enter and Tab remain available through their single face buttons; Y is Tab and Shift+Y is reverse Tab. Eight tier 5 and all sixteen tier 6 chords remain unassigned. Shift can still select text, and Ctrl plus a letter chord emits an ordinary keyboard shortcut.

## Frequency basis

The baseline separates English letter selection from programming punctuation. [Granite Code's published character frequencies](https://github.com/fohrloop/granite-code-ngrams) inform punctuation priority. Its corpus mixes Python, JavaScript, TypeScript, Rust and CSS; it strips leading indentation and is a source-text sample, rather than a record of keystrokes. Tab therefore stays an editing control, independent of corpus frequency.

For V1, shifted and unshifted characters share a physical US key slot, so their frequencies are added. For example, hyphen/underscore total 3.12%, 0/right parenthesis 2.53%, period/greater-than 2.44%, quotes 2.14%, comma/less-than 2.00%, semicolon/colon 1.78%, and 9/left parenthesis 1.74%. Each bracket/brace slot totals 0.89%. These sums use the rounded percentages in Granite's case-insensitive unigram table.

This supports giving punctuation its own easier slots after tier 1 and promoting brackets/braces to tier 4. Pair symmetry, recognizable digit groups and English letter coverage also guide placement; V1 is not a strict global frequency sort or a measured ergonomic optimum. Code language and actual editing habits can change priorities.

## Validation

`python3 tests/check-chord-recognizer.py` exercises the actual mapper frames without creating a host input device. It checks all 960 press/release order combinations for the 48 assigned chords, late Shift/Ctrl holds, reserved and invalid inputs, rolling-input cancellation and reset of unfinished gestures.

The real-application VM harness in [tests/check-gamepad-mapping.py](../tests/check-gamepad-mapping.py) checks every assigned chord with and without Shift, constituent suppression, release-only arrows and the existing navigation and lifecycle behavior. The [baseline VM mapping report](../.local/vm/storage-desktop-zm9c2afx/gamepad-mapping-report.json) passed all 25 acceptance groups, including 96 character cases covering 95 distinct printable ASCII characters. That VM run uses an earlier layout. The existing mapper frame checker passed for the current frequency-based profile; the recognizer and set of output keys are unchanged. The revised assignments have not been rerun in the VM. Physical controller diagonals and adjacent face presses still require a WIN Mini test.
