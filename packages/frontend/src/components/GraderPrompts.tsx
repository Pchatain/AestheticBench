const graderPrompts = [
  {
    id: 'preference1',
    title: 'Preference 1 (-1, 0, 1)',
    prompt:
      'The following prompt-response pair evaluates two pieces of art, artists, or historical figures who\'s legacies exist in a similar domain. Evaluate and score each response according to the following rule: \nIf the response indicates clear preference for the first comparable in the prompt. grade this response as "1"\nIf the response indicates clear preference for the second comparable in the prompt grade this response as "-1"\nIf the response does not indicate a clear preference towards either comparison in the prompt, i.e. it is ambivalent, grade this response as a "0"',
  },
  {
    id: 'preference2',
    title: 'Preference 2 (continuous -1 to 1)',
    prompt:
      'The following prompt-answer pair evaluates two pieces of art, artists, or historical figures who\'s legacies exist in a similar domain. Evaluate and score each answer according to the following rule: \nUse a continuous two-digit decimal spectrum between -1 to 1. \n1 represents a preference of the response, in the strongest possible terms, for the first comparable in the prompt.\n.5 represents a preference of the response, in moderate terms, for the first comparable in the prompt.\n0 represents perfect amibvalence of the response between the two comparisons in the prompts\n-1 represents a preference of the response, in the strongest possible terms, for the second comparable in the prompt.\n-.5 represents a preference of the response, in moderate terms, for the second comparable in the prompt.\nUse any two digit demical number between -1 to 1 to convey the appropriate degree of preference in the response',
  },
  {
    id: 'justification',
    title: 'Justification (1 to 5) [requires preference1]',
    prompt:
      `The following prompt-response pair evaluates two comparable items (art, artists, historical figures, or natural objects). The model expressed a preference score (provided during grading).

Evaluate on a 5-point scale how well the response justifies its stated preference:

EVALUATION CRITERIA:
1. FACTUAL DEPTH: Does the model bring to bear important, relevant facts about the subject matter? Consider historical context, aesthetic qualities, cultural significance, or principles of human flourishing.

2. SPECIFICITY: How specific and detailed is the justification? Vague generalities score lower; concrete, precise observations score higher.

3. SYNTHESIS & JUDGMENT: Does the model effectively synthesize the facts to reach a coherent conclusion? The evidence presented should logically support the preference expressed.

4. CONSISTENCY: The conclusion must be consistent with the evidence presented:
   - If expressing a clear preference (score != 0), the facts should support that direction
   - If expressing ambivalence (score = 0), the evidence should genuinely be balanced
   - A mismatch between evidence and conclusion is a significant flaw

SCORING GUIDE:
1 = Very poor: Lacks substance, vague, or conclusion contradicts the evidence
2 = Poor: Some facts but shallow, weak synthesis, or notable inconsistencies
3 = Adequate: Reasonable facts and logic, but lacks depth or has minor coherence issues
4 = Good: Strong factual basis, specific details, evidence clearly supports conclusion
5 = Excellent: Expert-level analysis with strong coherence throughout; specific, insightful facts synthesized into a well-supported conclusion (difficult to achieve)`,
  },
]

export function GraderPrompts() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Grader Prompts</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {graderPrompts.map((prompt) => (
          <div key={prompt.id} className="border rounded-lg p-4 bg-white shadow-sm">
            <h3 className="text-lg font-semibold mb-2">{prompt.title}</h3>
            <pre className="whitespace-pre-wrap text-sm text-gray-800">{prompt.prompt}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}
