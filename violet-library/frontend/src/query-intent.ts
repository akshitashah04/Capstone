const visaContext = /\b(?:visa|visas|immigration|nonimmigrant)\b|签证|簽證|वीज\u093c?ा/u;
const statusContext = /\bstatus\b/u;
const visaCode = /\b(?:[fmjbo]\s*-?\s*[12]|h\s*-?\s*1b)\b/g;
const studentVisa = /\b(?:student visas?|study visas?|nonimmigrant academic students?)\b|学[生習习]簽證|学[生習习]签证|學生簽證|留学签证|留學簽證|छात्र वी[ज़ज]ा|छात्र वीज़ा/u;
const unitedStates = /\b(?:u\s*s\s*a?|united states|american)\b|美国|美國|अमेरिका/u;

function normalize(text: string): string {
  return text.normalize('NFKC').toLowerCase().replace(/\p{Dash_Punctuation}/gu, '-')
    .replace(/\./g, ' ').replace(/\s+/g, ' ').trim();
}

function visaClasses(text: string): string[] {
  return [...new Set([...text.matchAll(visaCode)]
    .map(match => match[0].replace(/[\s-]/g, '')))];
}

export interface QueryIntent {
  embeddingText: string;
  visaClasses: string[];
  usStudentVisa: boolean;
  exactPhrases: string[];
}

export function interpretQuery(query: string): QueryIntent {
  const normalized = normalize(query);
  const codes = visaClasses(normalized);
  const hasVisaContext = visaContext.test(normalized) ||
    (statusContext.test(normalized) && codes.some(code => /^[fmj]/.test(code)) &&
      !/\b(?:formula (?:1|one)|motorsport|racing)\b/u.test(normalized));
  const classes = hasVisaContext ? codes : [];
  const usStudentVisa = classes.includes('f1') ||
    (classes.length === 0 && studentVisa.test(normalized) && unitedStates.test(normalized));
  const focus = query.trim().replace(
    /^(?:(?:i(?: am|'m) )?looking for|(?:can|could) you (?:find|recommend)(?: me)?|please (?:find|recommend))\s+/iu, '',
  ).replace(/\s+related books[.!?]*$/iu, '').trim();
  const topic = focus || query;
  return {
    embeddingText: usStudentVisa
      ? `${topic}\nU.S. student visa for academic study${classes.includes('f1') ? ' (F-1 nonimmigrant visa)' : ''}`
      : topic,
    visaClasses: classes,
    usStudentVisa,
    exactPhrases: [...query.matchAll(/"([^"]+)"|“([^”]+)”/gu)]
      .map(match => normalize(match[1] ?? match[2]))
      .filter(Boolean),
  };
}

export function supportsQueryIntent(metadata: string, intent: QueryIntent): boolean {
  if (!intent.visaClasses.length && !intent.usStudentVisa && !intent.exactPhrases.length) return true;
  const normalized = normalize(metadata);
  if (!intent.exactPhrases.every(phrase => normalized.includes(phrase))) return false;
  if (!intent.visaClasses.length && !intent.usStudentVisa) return true;

  // A class mentioned in immigration metadata carries more evidence than broad topic similarity.
  const classEvidence = [...normalized.matchAll(visaCode)].filter(match => {
    const position = match.index;
    const nearby = normalized.slice(Math.max(0, position - 24), position + 28);
    return visaContext.test(nearby) || statusContext.test(nearby);
  }).map(match => match[0].replace(/[\s-]/g, ''));
  const academicStudentVisa = studentVisa.test(normalized) && unitedStates.test(normalized);

  if (!intent.visaClasses.length) {
    return academicStudentVisa || classEvidence.some(code => code === 'f1' || code === 'm1');
  }
  return intent.visaClasses.every(code =>
    classEvidence.includes(code) || (code === 'f1' && classEvidence.length === 0 && academicStudentVisa));
}
