# On Strategy, Bias, and the Costs of Being Pragmatic
### A thought from the margins of a Survivor analytics project

*Jimmy Winslow — draft, [date]*

---

I've been building a model to predict voting outcomes on Survivor. Not metaphorically — I mean the CBS reality show, the one where eighteen strangers get dropped on an island and vote each other out one by one until one person wins a million dollars. The model uses survival analysis, network graphs, and Bayesian updating to estimate who gets eliminated each week, and it works reasonably well. Tribes that are physically weaker lose immunity challenges more often. Players who accumulate votes against them are more likely to get voted out. Players on the periphery of their alliance network are more exposed than players at the center.

While building it, I kept running into something uncomfortable in the data. Women and people of color get voted out earlier — statistically, consistently, across forty-nine seasons. The researchers who have documented this are careful to note that it isn't because these players are actually weaker. Experimental studies where observers rated contestant photos found no meaningful correlation between perceived weakness and being voted out first for women and BIPOC players specifically. The bias appears to be real, structural, and persistent. And it happens because individual players, making locally rational decisions in a high-pressure environment, collectively produce an outcome that none of them would necessarily endorse if you asked them directly.

This got me thinking about a political controversy I'd heard about — a podcast where two men argued that a Black woman running for a Senate seat in Texas was a strategically risky choice, and that pragmatic voters who shared her politics should consider backing the white male candidate instead. The argument was simple: racism and sexism exist, voters are biased, and therefore her probability of winning was lower. Supporting her was ideologically satisfying but strategically naive. If you want to win, you have to play the game as it is, not as you wish it were.

I want to think through why that argument is wrong. Not morally wrong — though it may be that too — but wrong as a piece of game theory. Wrong on its own terms.

---

## The Model They're Running

The strategic voting argument is an optimization problem. It looks like this:

> Given a fixed level of voter bias in the electorate, which candidate maximizes my probability of achieving my preferred policy outcome this election cycle?

If you accept that framing, the math is at least coherent. You're treating bias as a parameter — a number in the model, like terrain or weather — and you're asking which choice maximizes expected utility given that parameter. Voter bias is high in Texas. Therefore back the candidate who isn't penalized by it.

The problem is the word *fixed*.

Voter behavior is not a parameter. It's an outcome. Bias in electoral politics is not a natural constant like the speed of light. It is a social equilibrium — a pattern of behavior that persists because enough people act as though it will persist, and their acting as though it will persist makes it persist. This is what economists call an equilibrium with self-fulfilling expectations. It is what everyone else calls a self-fulfilling prophecy.

When you treat bias as fixed and optimize around it, you are not just accepting a constraint. You are contributing a data point that reinforces the constraint's stability. You are one more actor who behaved as though the bias was immovable, and your behavior is now part of the evidence that the bias is immovable.

---

## The Time Horizon Problem

The podcast hosts were running a one-election optimization. Winning this race. Getting this seat. That is a legitimate goal — I am not dismissing it. Senate seats matter. Policy outcomes matter.

But "be strategic" is a claim about rationality, and rationality requires specifying your objective and your time horizon. If your objective is *representation* — not just winning one race but building toward a world where a Black woman from Texas running for Senate is considered an obviously viable candidate — then the one-election frame is not just incomplete. It is actively counterproductive.

Consider what the long-run equilibrium looks like if strategic voters consistently abandon candidates from underrepresented groups whenever bias makes them seem like long shots:

- Those candidates lose, or are never recruited to run in the first place
- Campaigns internalize the lesson: don't run a Black woman in Texas
- Donors internalize the lesson: don't fund that candidate
- Voters internalize the lesson: that candidate type can't win here
- Future candidates from those groups face an even steeper hill
- The bias, which was never actually fixed, becomes more entrenched

The strategic voter got their preferred Senator this cycle. But they paid for it with a reinforced expectation that will cost representation for the next decade. That is not strategy. That is mortgaging the future for a short-term win — which is exactly the kind of decision that looks rational in a one-period model and catastrophic in a multi-period one.

The correct optimization problem is not:

> max P(win this election | bias = fixed)

It is:

> max E[representation outcomes over time | my vote, where bias is a function of accumulated prior choices]

Once you write it that way, the strategic case for abandoning the less "electable" candidate looks much weaker.

---

## Who Bears the Cost

There is another thing the strategic voting argument tends to obscure: the asymmetry of who is being asked to be pragmatic.

The voters most likely to be told "be strategic, back the viable candidate" are the ones whose communities have been underrepresented for longest. They are asked to make a sacrifice — to set aside a candidate who looks like them, who came from where they came from, who is running explicitly for them — in the name of collective pragmatism. And this request is made repeatedly. Every election cycle. For generations. While the structural conditions that make the sacrifice necessary are addressed, if at all, slowly and incompletely.

The voters for whom the "viable candidate" is just the default — who have never had to think about whether someone who looks like them can win — are rarely asked to be pragmatic about their own representation. Their representation is the baseline. Pragmatism is a tax levied almost exclusively on people who are already paying the highest costs of the status quo.

This is not an argument against pragmatism. It is an argument that the pragmatism calculus is incomplete when it ignores who bears its costs.

---

## Back to Survivor

The Survivor data is a clean version of the same problem, and I think that is why it has stayed with me.

Nobody on Survivor wants to be the villain who voted out the person of color because of bias. In exit interviews, in confessionals, in post-season retrospectives, players almost never articulate a preference for keeping white men in the game. And yet the aggregate pattern holds across fifty seasons. Women get voted out first more often. BIPOC players get voted out first more often. The individual decisions that produce this pattern are mostly made by players who would sincerely reject the bias if you named it directly.

What's happening is that each player is making a local calculation — "my tribe needs to be strong for the next challenge, and I perceive this player as weaker" — without modeling the fact that their calculation is one instance of a general pattern, and the general pattern has a structural tilt. The bias doesn't live in any one vote. It lives in the aggregate of individually justifiable decisions, each of which feels rational in isolation.

This is the same structure as the strategic voting argument. Each voter is making a local calculation — "I want to win this Senate race, and I perceive this candidate as less viable" — without modeling the aggregate effect of that calculation repeated across millions of voters, election after election. The individual decision is locally coherent. The aggregate is corrosive.

---

## What I Actually Believe

I want to be direct about where I land, because this is not just an analytical question for me.

I think the podcast hosts were wrong, and I think they were wrong in a way that matters. Not because they were racist — I don't know that they were — but because they presented a one-period optimization problem as though it were settled strategic wisdom, without acknowledging the feedback loop, without naming who bears the costs, and without considering what it means to call something "strategic" when the time horizon is long enough to include your own children.

I also think the question is genuinely hard, and that people who disagree with me about it are not necessarily making an error of values. They may simply have a shorter time horizon, or weight the present Senate seat more heavily than I do, or have less faith that incremental representation gains compound over time. Those are reasonable places to disagree.

What I don't think is reasonable is treating the argument as obviously correct because it invokes the word "strategy." Strategy requires a fully specified objective function. It requires a time horizon. It requires modeling how your decision interacts with others' decisions over time. When you do all of that, the case for strategic abandonment of underrepresented candidates looks much less like clear-eyed pragmatism and much more like a localized optimization that externalizes its costs onto exactly the people who can least afford to absorb them.

The tribe has spoken. The question is what we're actually voting for.

---

## A Note on This Project

This essay lives in the notes directory of a Survivor analytics project. That might seem like an odd home for it, but I think the connection is real.

One of the things I find most interesting about data science — and about working with Survivor data specifically — is how often the same mathematical structure appears in wildly different contexts. Survival analysis works on cancer trial data and on Tribal Council elimination data. Network centrality measures work on social networks and on alliance graphs. Bayesian updating works on fraud detection and on weekly threat assessments for a reality TV show.

The political argument above has the same structure as a problem in my model: a system of individually rational decisions producing a biased aggregate outcome, which then gets mistaken for a fixed feature of the environment rather than an equilibrium that could shift under different collective choices. Recognizing that structure in one context makes it easier to see in another.

That's what I think data science is actually for.

---

*This is a draft. It will be revised. It may eventually become a blog post, a LinkedIn article, or just a note I return to when I need to remember why the math matters.*
