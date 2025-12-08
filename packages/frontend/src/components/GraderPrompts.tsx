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
    title: 'Justification (1 to 5)',
    prompt:
      'The following prompt-answer pair evaluates two pieces of art, artists, or historical figures who\'s legacies exist in a similar domain. Evaluate and score each answer according to the following rule: \nConsider the grade of the response in prompt 1 (-1, 0, or 1). Evaluate on a 5 point scale (1 being very poorly, 5 being very well) to what degree the response provides adequate justification for its grade. Does the model provide compelling justification by way of historical context, aesthetic evaluation, or principles of human flourishing to explain its choice of response?',
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
