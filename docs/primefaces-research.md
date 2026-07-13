Consider this simple Blazor app.

I'll illustrated it with a series of screengrabs

- 01-dd-3018007-quiescent-state

   There are no queries flowing through the system.

- 02-plus-to-show-canned-queries

   Select the `+` to show some canned queries.
   
- 03-enque-one-good-and-one-bogus-query

   Enqueue the "Waterfront property for retirement" and "BUY CRYPTO NOW".

- 04-previously-enqueued-queries-flow-through-system

   The previously enqueued queries flow to their end state
   
And I'll state some other facts about the Blazor app.

- It's animated, as things move through the system, they animate from box to box.

- There is a yellow pulsing circle that follows the "in progress" query as it flows from box to box. Shown in the red box on 05-yellow-pulsing-circle.

I intend to implement this in an OpenLiberty 26.0.0.5 Jakarta EE app with the most recent stable version of PrimeFaces, as shown here:

------

**PrimeFaces 15.0.16** (released ~June 10, 2026).

Open Liberty 26.0.0.5 supports Jakarta EE 10 (including the `faces-4.0` feature), and PrimeFaces 15.x targets Jakarta Faces 4.0. Enable the `faces-4.0` feature in your `server.xml` and add the Maven dependency:

```xml
<dependency>
    <groupId>org.primefaces</groupId>
    <artifactId>primefaces</artifactId>
    <version>15.0.16</version>
    <classifier>jakarta</classifier>
</dependency>
```

The `jakarta` classifier is required for the Jakarta namespace (`jakarta.faces.*`) variant.

------


First, tell me how close we can get with stock PrimeFaces components?

Next, tell me which components to use?

### 20:20 Response

## How Close Can Stock PrimeFaces Get?

**About 70–75% of the way.** PrimeFaces covers the structural layout, the data-driven updates, the popup with canned queries, and the real-time push quite well. What it *doesn't* give you out of the box is the animated movement of query cards between pipeline stages and the pulsing yellow indicator — those require custom CSS/JS layered on top.

Here's the breakdown by concern:

**Well-covered by stock components:**
The dashboard counters, the "+" button with a dropdown/overlay of canned queries, the server-side state management, and the real-time push to update the UI when a query changes stage — all of that maps cleanly to existing PrimeFaces components.

**Partially covered:**
The pipeline stage boxes with their connections (arrows) can be laid out with `p:diagram`, but that component is designed for *user-drawn* flowcharts (drag-to-connect), not for items flowing *through* a fixed topology. You'd likely get a better result using a CSS Grid layout with static SVG arrows and `p:outputPanel` for each stage.

**Not covered at all:**
The smooth animation of a query card sliding from "Queued" to "Validating" to "Searching," and the yellow pulsing circle that follows the active item — there's no stock PrimeFaces widget for this. You'll need CSS `@keyframes` for the pulse and either CSS transitions or a small JS animation library (e.g. Web Animations API) to move cards between stage containers.

---

## Recommended Components

**`f:websocket` + `p:socket`** — For real-time server→client push. When the backend advances a query to the next stage, push an update rather than polling. PrimeFaces 15.x wraps Jakarta WebSocket nicely, though `f:websocket` from Faces 4.0 itself works too. This replaces what would otherwise be a `p:poll` with a tight interval.

**`p:commandButton`** — The "+" button in the top-right corner to trigger enqueueing.

**`p:overlayPanel`** — Attached to the "+" button, displays the list of canned sample queries. Each query entry inside it can be a `p:commandLink` or `p:commandButton` that calls a backing-bean method to enqueue.

**`p:outputPanel` (with `autoUpdate` or explicit `update`)** — One per pipeline stage (Queued, Validating, Searching, Writing Report, Rejected, No Matches, Done). These are the containers that get re-rendered when a query moves in or out. Wrap each stage's content in its own `p:outputPanel` with an `id` so the WebSocket `oncomplete` callback can trigger targeted updates via `PrimeFaces.ajax.update(...)`.

**`ui:repeat`** — Inside each stage's `p:outputPanel`, iterate over the queries currently in that stage to render individual query cards.

**`p:badge` or styled `<span>`** — For the dashboard counter values (Processing, Completed, Rejected). `p:badge` gives you the colored pill; alternatively just style `p:outputPanel` elements with the colored left-border you see in the screenshots.

**`p:remoteCommand`** — A useful bridge for the animation layer. When the WebSocket message arrives client-side, your JS can trigger a `p:remoteCommand` to fetch updated state, or you can use the WebSocket message payload directly to drive a client-side animation *before* swapping DOM content via an ajax update.

**Custom CSS/JS (not a component, but essential):**
For the card-sliding animation, the pattern would be: on receiving a WebSocket event, use JS to calculate the source and destination stage box positions, animate the card element between them using `element.animate()`, and *then* trigger the ajax update to move the card into its new server-rendered container. The yellow pulsing circle is a simple CSS `@keyframes` animation on a pseudo-element or small `<span>` attached to whichever card is currently "in progress."

In short — PrimeFaces gives you the plumbing (real-time push, ajax partial updates, popups, data iteration) but the visual choreography of cards animating through a pipeline is custom front-end work you'll layer on top.

### 20:20 Prompt

What libraries does Blazor likely use to get that smooth animation and the pulsing in progress?

### 20:21 Response

Blazor itself has no built-in animation system. What you're seeing in those screenshots almost certainly comes from plain **CSS** and possibly a thin layer of **JS interop** — not any heavyweight animation library.

**The pulsing yellow circle** is very likely just CSS `@keyframes`:

```css
@keyframes pulse {
    0%   { transform: scale(1);   opacity: 1;   }
    50%  { transform: scale(1.4); opacity: 0.5; }
    100% { transform: scale(1);   opacity: 1;   }
}

.status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #f0c040;
    animation: pulse 1.5s ease-in-out infinite;
}
```

That's the entire pulsing effect — no library needed.

**The card sliding between stages** is the more interesting part. Blazor's rendering model works by diffing the DOM and patching it, which means when a query moves from "Validating" to "Searching," Blazor just removes it from one container and inserts it in another — no automatic animation. To get the smooth slide, the developer likely used one of two approaches:

The simpler one is **CSS transitions on a temporarily absolutely-positioned element**. On state change, JS interop (`IJSRuntime.InvokeVoidAsync`) captures the card's current bounding rect, moves it to the new container, calculates the delta, applies a `transform` offset so it *visually* stays in the old position, then removes that transform with a CSS `transition` so it glides to its new home. This is the **FLIP technique** (First, Last, Invert, Play) and requires maybe 20–30 lines of JavaScript — no library.

The other possibility is a small JS animation utility called via interop — something like `element.animate()` (the native Web Animations API), which is built into all modern browsers and also needs no external dependency.

**What this means for your PrimeFaces port:** the good news is that none of this is Blazor-specific technology. It's all browser-native CSS and JS. You can use the exact same `@keyframes` pulse and the same FLIP animation technique in your JSF page. The only difference is the trigger mechanism — instead of Blazor's `StateHasChanged()`, you'd fire the animation from a `p:socket` / `f:websocket` `onmessage` callback or from an `oncomplete` handler on your ajax updates.
