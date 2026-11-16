# Command names: primaries and custom phrases

## Now
Every command has one **primary** phrase, which is the one the app uses and shows. Only primaries are loaded into the
grammar. The primary is the phrase the code and the docs refer to.

## Planned
Each command can also have up to two **custom** phrases, `custom_1` and `custom_2`, and no more. A custom phrase does
the same thing as the primary. For example, a user who doesn't like "toggle scorecard" can have "show scorecard" and
"hide scorecard" as customs, and both run the same logic as the primary.

Later, DYK gets a screen that lists the commands. On it, a user can:
- enter a custom phrase for each command (up to two),
- tick a checkbox per command to enable or disable loading it into the grammar.

Other settings for this screen are for later. Until then, use primaries only.

## Rules for the design
- The primary is always there. Customs are optional, and never more than two per command.
- A custom phrase must be unique across all commands, or the grammar can't tell them apart.
- A disabled command loads nothing into the grammar, so it can't be heard at all.
