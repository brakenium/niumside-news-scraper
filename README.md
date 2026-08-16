# PlanetSide 2 news and patch notes archive

An automated archive of the PlanetSide 2 news and patch-note feeds.

The project retrieves the feed data embedded in the PlanetSide 2 patch-notes
page and preserves it as JSON. Previously one was able to use the forum RSS feed, but they discontinued the forum and no longer update the RSS. This repo extracts news and patch notes from the website and converts the website's `SOE.Feeds.news.data` and `SOE.Feeds.patchNotes.data` into JSON stored in this repo

## Data

The repository contains two versions of each feed.

### Current feeds

- `data/news.json`
- `data/patch-notes.json`

These files contain the feed data currently exposed by the PlanetSide 2
website.

The website currently exposes 50 entries in each feed, although the scraper
does not depend on that number.

### Archives

- `data/archive/news.json`
- `data/archive/patch-notes.json`

These files contain the cumulative archive.

Every newly discovered entry is added to the corresponding archive. Entries
are identified by their `pageName`.

Entries are never removed from the archive when they disappear from the
current PlanetSide 2 feed.

The complete source objects are preserved rather than reducing them to a
custom schema.

## GitHub Pages

The GitHub Pages site exposes the same data:

```text
/
├── index.html
├── news.json
├── patch-notes.json
└── archive/
    ├── news.json
    └── patch-notes.json
```
