## Plotly Heatmap Grade Explorer

### Branch
Check out a new branch `plotly-grade-heatmaps` from `chatain-jan-19`.

### New Page: "Grade Explorer" (sidebar entry)
A new page with **8 Plotly heatmaps** (one per question), each showing:
- **X-axis**: Prompts (~48, labeled by UID or short question text)
- **Y-axis**: Models
- **Color**: Grade value for that (model, prompt, question) tuple
- **Click handler**: Clicking a cell opens a modal/popup displaying the **prompt text** and the **model's response**

#### Questions (from `grader_prompts.py` + TUI):
| Question | Name | Scale | Data Source |
|----------|------|-------|-------------|
| Q1 | Relativism | Yes/No (0/1) | Graded CSVs (`Q1_Relativism_Score`) |
| Q2 | Preference | -1, 0, 1 | Graded CSVs (`Q2_Preference_Score`) |
| Q3 | Evidence | -1, 0, 1 | Graded CSVs (`Q3_Evidence_Score`) |
| Q4 | Justification | 1-5 | Graded CSVs (`Q4_Justification_Score`) |
| Q4.1 | Factual Depth | 0/1 | DB annotations (`q4_1_score`) |
| Q4.2 | Specificity | 0/1 | DB annotations (`q4_2_score`) |
| Q4.3 | Synthesis | 0/1 | DB annotations (`q4_3_score`) |
| Q4.4 | Consistency | 0/1 | DB annotations (`q4_4_score`) |

### Steps

1. **Create branch** `plotly-grade-heatmaps`

2. **Install Plotly frontend deps**
   ```
   cd packages/frontend && npm install react-plotly.js plotly.js-dist-min && npm install -D @types/react-plotly.js
   ```

3. **Backend: New API endpoint** `GET /api/grades/heatmap`
   - Returns all (model, prompt_uid, question_text, response_text, topic) tuples with their grades for Q1-Q4 (from CSVs) and Q4.1-Q4.4 (from DB annotations)
   - Shape: `{ data: [{ uid, model, topic, question, response, q1, q2, q3, q4, q4_1, q4_2, q4_3, q4_4 }] }`
   - Merges CSV grades + DB annotation scores in one response

4. **Frontend: New `GradeExplorer.tsx` component**
   - Fetches from `/api/grades/heatmap`
   - Model/topic filter checkboxes (reuse pattern from Analytics)
   - Renders 8 `<Plot>` heatmaps (one per question), each wrapped in a `<CollapsibleSection>`
   - Each heatmap: `type: 'heatmap'`, `x=prompt_uids`, `y=model_names`, `z=grade_matrix`, with appropriate colorscale per question type
   - `plotly_click` event handler → opens a modal showing the prompt + response for that cell

5. **Frontend: Response Modal component**
   - Displays: prompt text, model name, full response text, all grades for that tuple
   - Closable overlay/modal

6. **Wire into App.tsx + Sidebar** as new page "Grade Explorer"

7. **Migrate ModelComparison.tsx** radar chart from recharts to Plotly (`scatterpolar` traces)

8. **Verify**: `npm run build && npm run lint` in frontend

### Notes
- All 8 heatmaps displayed at once (each in collapsible sections), no dropdown needed
- Cells with no grade data shown as grey/null
- Existing Analytics and ModelComparison pages remain untouched (except ModelComparison gets Plotly migration)
- `recharts` stays installed (Analytics + JustificationExperiment still use it)
