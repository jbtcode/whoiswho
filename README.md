# WHO IS WHO Application

## Context

Whenever new people join the company, we want to know who is who. Additionally, new people should get to know their colleagues. Therefore, we want to make an internal application that gamifies getting to know your colleagues

## Concept

Data storage of each person with personal and professional information

* Picture
* Manager
* Hobbies
* etc

Goal would be to get to know your colleagues a bit better via an application on this data. 

## Capabilities

* Profile page: Personal page where you can update, add, or remove your own information
* Search page: When I type a (sound-ex) name, find the person you are looking for
  * Can we search on characteristics? Eg, I am looking for a blond guy with glasses
  * (Extension) Historical page:
    * We talked about a client that they used to work on
    * WHOZ: Search based on skillset
  * Who likes to cycle? -> Invite people for a bike ride session
-> Connect to internal application (WHOZ, Odoo, TeamTailor, Viva Engage (teams), Unit4, etc.) where all professional data is coming from ; Personal information needs to be able to be modified by the individual itself
  * Data policy: Only use professional data, or personal data you updated yourself

* New joiners (or soon-to-be joiners)
  * Extension: Leavers?
* Quiz-page: Different 'mini games' to get to know the people in the company
  * TRUE/FALSE questions
  * Match 10 images with 10 names
  * Match the pet with the owner
  * etc.

* We need to be able to add new pages easily
  * Internal competitions
  * New mini-games
  * Other interesting extensions
  * New sets of data (NoSQL-like storage would be ideal)

## Architecture

* Storage account and table storage
* WebApplication: Azure Web App
  * Company SSO to link with account
* DevOps integration (git repository)
* Integrations to existing tools (APIs)
  * WHOZ
  * Teams
  * Odoo
  * TeamTailor
      -> Watch out for fetched data
      -> If hired, already prepare the profile (start date, name, team, skills, etc.)
  * Unit4

