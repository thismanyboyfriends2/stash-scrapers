# Stash Scrapers

Scraper definitions that Stash installs from this repo's source index to fill in metadata for its library.

## Language

**Scraper**:
A YAML definition, optionally with a script, that Stash runs to return a fragment of metadata for the user to review. It is given only its input fragment, never a connection back to Stash.
_Avoid_: plugin (a different Stash extension point)

**Plugin**:
A Stash extension that runs tasks or hooks with a connection back to Stash, meant for acting on the library rather than returning metadata.
_Avoid_: scraper

**Image**:
A still-image item in the Stash library, which can have Performers attached.
_Avoid_: picture, photo, image file

**Performer image**:
The profile picture shown for a Performer, set from an Image or a URL.
_Avoid_: profile pic, avatar, headshot

**Fragment**:
The partial record of a Scene, Performer, Image, etc. that Stash passes to a Scraper as input and expects back as output.
_Avoid_: payload, input object
