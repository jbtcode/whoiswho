# WHO IS WHO Application

## Context

Whenever new people join the company, we want to know who is who. Additionally, new people should get to know their colleagues. Therefore, we want to make an internal application that gamifies getting to know your colleagues.

## Concept

Data storage of each person with personal and professional information.

* Picture
* Manager
* Hobbies
* etc.

The goal is to get to know your colleagues a bit better via an application on this data.

## Capabilities

* Profile page: personal page where you can update, add, or remove your own information.
* Search page: when you type a (sound-ex) name, the application can find the person you are looking for.
  * Can we search on characteristics? Example: looking for a blond guy with glasses.
  * Extension: historical page.
    * We talked about a client that they used to work on.
    * WHOZ: search based on skillset.
  * Who likes to cycle? -> invite people for a bike ride session.
* Connect to internal applications (WHOZ, Odoo, TeamTailor, Viva Engage, Unit4, etc.) where professional data comes from; personal information should be modifiable by the individual itself.
  * Data policy: only use professional data, or personal data you updated yourself.
* New joiners (or soon-to-be joiners).
  * Extension: leavers?
* Quiz page: different mini-games to get to know colleagues.
  * TRUE/FALSE questions.
  * Match 10 images with 10 names.
  * Match the pet with the owner.
  * etc.
* We need to be able to add new pages easily.
  * Internal competitions.
  * New mini-games.
  * Other interesting extensions.
  * New sets of data (NoSQL-like storage would be ideal).

## Architecture

* Storage account and table storage.
* Web application: Azure Web App.
  * Keyrus SSO to link with the account.
* DevOps integration (Git repository).
* Integrations to existing tools (APIs).
  * WHOZ.
  * Teams.
  * Odoo.
  * TeamTailor.
    * Watch out for fetched data.
    * If hired, already prepare the profile (start data, name, Keyrus team, skills, etc.).
  * Unit4.

