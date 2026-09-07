# Burrows Field Fixtures

A simple GitHub Pages site showing upcoming football fixtures at **Burrows Field**.

## How it works

The site uses the official FA Full-Time embedded feed supplied by the club:

- Full-Time feed ID: `933106153`
- FA embed script: `https://fulltime.thefa.com/client/api/cs1.js`
- The feed is loaded directly in the browser.
- JavaScript filters the rendered fixture list to venues matching **Burrows Field**, including pitch names such as `BURROWS FIELD #1`, `BURROWS FIELD #2`, etc.

This means there is no server-side scraper, no GitHub Actions job and no stored fixture data to maintain.

## Why this approach

FA Full-Time protects its fixture pages against automated scraping. Using the official embedded feed avoids that problem and means fixture information is supplied directly by Full-Time whenever the page is opened.

## Deployment

The repository is intended to be published with GitHub Pages. After changes are pushed to `main`, GitHub Pages serves `index.html` directly.

## Important

Do not replace the `lrcode` value or the FA Full-Time `cs1.js` script unless the club supplies a new official feed code.
