Some things you might consider editing the website to say.

# Front page

There's a lot of filler content here.

# Rules

If you plan to keep the website running until some "close date" after the end of the hunt, you can say so here. Also review all the rules to make sure you and your puzzles agree with them. For example, if looking at the HTML/JavaScript/CSS source will be necessary for any puzzle in your hunt, or if you want to explicitly tell teams not to do so by a honor code system, you should change that rule.

# Culled from the FAQ

Questions you might want to answer, for which we removed GPH-specific answers:

- Do I need to have an X-person team?
- How many puzzles will there be? ("Around X." for a round number X.)
- What exactly happens when the hunt ends? (You can use e.g. `{% format_time end_time '%B %d' %}` in the template.)
- Can I write code that interacts with the puzzles / server?
- Who's running this hunt?
- Are there any prizes?
- Is there a physical component to the hunt? Will I ever need to be in a particular location to solve a puzzle?
- Is there a registration deadline?

# Archive / Other Pages

There's an archive page where you can link to past hunts and such, but you can just delete the link (from `base.html`) and the page if you don't have anything like that.

You can also add other links in the top bar displayed on every page in the same place, in `base.html`. This repo already has a story page, an errata/updates page, and a wrapup page, which are all hidden by default and controlled by boolean flags in `hunt_config.py`.
