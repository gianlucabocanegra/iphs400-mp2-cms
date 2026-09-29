# Golf & Country Club of Trujillo CMS

A small CMS where the club's office staff write news, events and the weekly menu, and members read them on a public site. The console is in English; the public site is in Spanish, so each term below lists its Spanish label.

## People

**Admin** (Administrador):
A staff member who manages Pages and Users, and can do everything an Editor can.
_Avoid_: superuser, owner

**Editor** (Editor):
A staff member who writes, publishes and fixes any Post, and nothing else. An Editor can never touch Pages or Users.
_Avoid_: author (as a role), staff, poster

**Author** (Autor):
The User who originally wrote a Post or Page. Stays the original writer even when someone else edits it. Visible only in the console, never to Members. An attribute of content, not a role.

**User** (Usuario):
A login belonging to one staff member, with exactly one role: Admin or Editor. Users are never deleted, only Deactivated.
_Avoid_: account, member (members are readers, not Users)

**Deactivated** (Desactivado):
A User who can no longer log in. Their content and authorship stay untouched. An Admin can't deactivate or demote themselves, so the club always has an Admin.
_Avoid_: deleted, removed, banned

**Member** (Socio):
A club member or family member who reads the public site. Members never log in.
_Avoid_: user, reader

## Content

**Post** (Publicación):
Dated content that appears in a feed, not as its own navigation entry. Every Post is exactly one kind: News, Event or Menu.
_Avoid_: article, entry

**News** (Noticia):
A Post announcing club news.

**Event** (Evento):
A Post about something happening at the club, with an Event date.

**Event date** (Fecha del evento):
When an Event happens: a start date, an optional start time and an optional end date for multi-day events such as weekend tournaments. Distinct from when the Post was written or published.

**Upcoming** (Próximos eventos):
An Event whose end date (or start date, if there's no end date) is on or after the day of the last Export. A weekend tournament stays Upcoming while it is happening. Decided at Export, not when a Member visits.
_Avoid_: future, current

**Menu** (Menú de la semana):
A Post holding the restaurant's menu and prices for one week.
_Avoid_: menu page

**Current menu** (Menú actual):
The newest Live Menu. It's the only Menu shown on the Home page.

**Menu archive** (Menús anteriores):
The public list of every Live Menu other than the Current menu.

**Page** (Página):
Standing content with its own navigation entry, such as rules, membership or about. Only Admins manage Pages, and they set the navigation order.
_Avoid_: static page

**Home page** (Inicio):
The generated public front page showing the Current menu, Upcoming Events and the latest News. Not a Page; nobody writes it.
_Avoid_: landing page, index page

**Navigation** (Navegación):
The public site's top links: Home page first, then the three fixed entries (News, Events, Menu archive), then Pages in Admin-set order.
_Avoid_: menu (reserved for the restaurant Menu)

**Slug**:
The last part of a piece of content's public address, made from its title with accents stripped. Can be edited only before first publish. Never contains a date.
_Avoid_: permalink, URL

## Publishing

**Draft** (Borrador):
Content that exists only in the console. A Draft never reaches the public site.

**Published** (Publicado):
A status only: content marked as belonging on the public site. Becomes Live at the next Export.
_Avoid_: live (when you mean the status)

**Confirmation** (Confirmación):
The explicit second step required before any change to what Members will see: publishing, unpublishing, deleting, or saving edits to Published content.
_Avoid_: approval, review

**Unpublish** (Despublicar):
Returning Published content to Draft, so it disappears from the public site at the next Export.
_Avoid_: hide, archive

**Export** (Exportación):
Rendering all Published content into the public site and deploying it. Run by the developer, never by the office.
_Avoid_: publish, deploy, build

**Live** (En línea):
Content that is on the public site right now, because it was Published at the last Export.
_Avoid_: published (when you mean visible to Members)
