#!/usr/bin/env python3
"""
Performer Image Scraper
Sets the current image being scraped as the attached performer's profile picture.
Requires exactly one performer to be attached to the image.
"""
import json
import sys

try:
    from py_common import log
    from py_common import graphql
    from py_common import util
except ModuleNotFoundError:
    print(
        "py_common not found. Add the CommunityScrapers source to Stash:\n"
        "https://stashapp.github.io/CommunityScrapers/stable/index.yml",
        file=sys.stderr
    )
    sys.exit(1)




def get_image_performers(image_id):
    """Get performers associated with a specific image."""
    query = """
        query FindImage($image_id: ID!) {
            findImage(id: $image_id) {
                id
                title
                paths {
                    image
                }
                performers {
                    id
                    name
                    image_path
                }
            }
        }
    """
    variables = {"image_id": image_id}
    result = graphql.callGraphQL(query, variables)
    return util.dig(result, "findImage")


def update_performer_image(performer_id, image_url):
    """Update a performer's profile image."""
    query = """
        mutation PerformerUpdate($input: PerformerUpdateInput!) {
            performerUpdate(input: $input) {
                id
                name
                image_path
            }
        }
    """
    variables = {
        "input": {
            "id": performer_id,
            "image": image_url
        }
    }
    result = graphql.callGraphQL(query, variables)
    return util.dig(result, "performerUpdate")


def announce_result_to_stash(result):
    """Output result to Stash via stdout."""
    if result is None:
        result = {}
    print(json.dumps(result))
    sys.exit(0)


def main():
    # Read input from stdin
    stdin = sys.stdin.read()
    fragment = json.loads(stdin)

    # Extract image ID from the fragment
    image_id = util.dig(fragment, "id")
    if not image_id:
        log.error("No image ID provided in fragment")
        announce_result_to_stash(None)

    log.debug(f"Processing image ID: {image_id}")

    # Query Stash to get image and its performers
    image_data = get_image_performers(str(image_id))

    if not image_data:
        log.error(f"Image {image_id} not found in Stash")
        announce_result_to_stash(None)

    performers = util.dig(image_data, "performers", default=[])
    image_url = util.dig(image_data, "paths", "image")

    if not image_url:
        log.error(f"Image {image_id} has no image path")
        announce_result_to_stash(None)

    # Validate exactly one performer
    if len(performers) == 0:
        log.error(f"Image {image_id} has no performers attached")
        announce_result_to_stash(None)
    elif len(performers) > 1:
        performer_names = ", ".join([p.get("name", "Unknown") for p in performers])
        log.error(f"Image {image_id} has multiple performers: {performer_names}")
        announce_result_to_stash(None)

    # Extract the single performer
    performer = performers[0]
    performer_id = performer.get("id")
    performer_name = performer.get("name", "Unknown")

    log.debug(f"Updating performer '{performer_name}' (ID: {performer_id}) with image {image_url}")

    # Update the performer's profile image
    updated_performer = update_performer_image(performer_id, image_url)

    if not updated_performer:
        log.error(f"Failed to update performer {performer_id} image")
        announce_result_to_stash(None)

    log.info(f"Successfully updated performer '{performer_name}' profile image")

    # Return empty result - the performer's image has been updated
    announce_result_to_stash({})


if __name__ == "__main__":
    main()
