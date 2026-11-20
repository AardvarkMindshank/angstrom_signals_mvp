# Video theme music

Put the theme track here as `theme.mp3`. It plays under the opening card (its start) and the closing card (its
end), below the voice. Record where it came from and its licence below.

| File | Source | Licence |
|---|---|---|
| theme.mp3 | "Chill Logo Design" by bombinsound, Pixabay (track 499531), chosen by the owner, 6 Nov 2026 | Pixabay Content License: free for commercial use, no attribution required |
| briefing_bed_sunny.mp3 | "1-Sunshine", Pixabay, chosen and graded 1 (most positive) by the owner, 20 Nov 2026 | Pixabay Content License |
| briefing_bed_fair.mp3 | "2-Springtime", Pixabay, graded 2 by the owner, 20 Nov 2026 | Pixabay Content License |
| briefing_bed_changeable.mp3 | "3-Cloudy", Pixabay, graded 3 by the owner, 20 Nov 2026 | Pixabay Content License |
| briefing_bed_rough.mp3 | "4-Rainy", Pixabay, graded 4 by the owner, 20 Nov 2026 | Pixabay Content License |
| briefing_bed_stormy.mp3 | "5-Stormy", Pixabay, graded 5 (least positive) by the owner, 20 Nov 2026 | Pixabay Content License |

## Morning briefing

The 🎧 morning briefing (briefing_audio.py) uses `theme.mp3` at its start and end. An optional quiet music bed
under the voice goes here as `briefing_bed.mp3` (looped, at about 8% volume). Record its source and licence above.
Or one bed per morning's weather, picked from the markets' mood: `briefing_bed_sunny.mp3`, `briefing_bed_fair.mp3`,
`briefing_bed_changeable.mp3`, `briefing_bed_rough.mp3`, `briefing_bed_stormy.mp3` (briefing.weather).

The weather track plays the whole briefing: loud on its own for the opening, dipping well under the voice, and
swelling back for the close (briefing_audio.mix_command). Stored as mono 96 kbps copies of the owner's files.
