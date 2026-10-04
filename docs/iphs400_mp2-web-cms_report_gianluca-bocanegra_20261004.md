# MP2 Report: Web CMS for the Golf & Country Club of Trujillo

Gianluca Bocanegra · IPHS 400 · October 2026

## What I built

I built a CMS for the Golf & Country Club of Trujillo (the club in Peru that my family belongs to, and where I grew up playing tennis). The club staff can log in, write news, pages and events, post the weekly menu, and publish it all as a public website on GitHub Pages. There are two roles. An Admin can do everything, including managing users. An Editor can write and publish content but can't touch users or the rules pages. The whole website is in Spanish, because that's what the members read and that's the main language we speak in Peru. The admin console is in English to keep it simple, and CONTEXT.md maps each English term to its Spanish label.

My grill decisions:

1. The menu is a post, not a page. The AI recommended making it a page, and I said no. The menu changes every week, so make it a post (Menú de la semana), not a page. That way an Editor can update it and still can't touch the rules pages.
2. Events get an optional end date. The AI recommended a date plus an optional start time, and also putting multi-day events in the body text. I wrote: "Golf tournaments here run over a weekend, so 'Sat to Sun' should be a field, not just text in the body." The 10–11 October tournament on the live site uses it.
3. Spanish for the public site only. The AI recommended Spanish everywhere. I split it, as explained above.

## One place the AI got it wrong, and how I caught it

In T02 (Posts, issue #3), the review caught that the Markdown cleaner let mailto: links through on images. My spec says only http and https. The code review caught it before I closed the ticket.

In T04 (issue #5), the review found a database change with no test. I added one that opens an old-format database and checks that the app still starts.

## What I used

I used Claude Code with the Pocock skills: grill-with-docs, to-spec, to-tickets, implement and code-review. I started Claude Code from my home folder at the beginning, so /tdd and /grill-with-docs weren't found. Skills only load from inside the project folder. That's why the first two exercises were written directly, without red-green steps. I also used the GitHub CLI for issues and Pages.

## Plan vs actual

- 5-hour windows: I planned about 3 and used 4. The meter reset three times.
- Grill, spec and tickets: I planned 25% of a window and used about 3%.
- Implement and review: I planned 15% per ticket. The tickets summed to 46% across eight tickets, an average of about 6% each. T08 shows 19%, but that is inflated because the phase file stayed on T08 for a long session that also did the secret-key fix, an audit and the screenshots.
- Tickets: I planned 9 and built 8.
- Weekly usage: I expected to end near 57%. The most it reached was 24%.

The ledger covers 12 of the 15 transcripts. Sessions 01, 11 and 13 were only a /clear command, so they have no usage data. For T03, the commit that closes the issue only touches settings, the README and tests. The real T03 work is in commit 4df7e5b.

## What I would improve

- A proper 403 page for Editors. Right now it's a plain error message.
- Revision history, so the club can undo a bad edit.
- Test the site with club staff. I haven't shown it to them yet.
