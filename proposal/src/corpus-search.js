import {stemmer} from 'stemmer';
const STOP=new Set('a an the and or but to of for in on at by with from as is are was were be been being it its this that these those i me my we our you your they their he she his her how what why when where which who about into through between among over under than then can could should would will do does did have has had not no all some any also more most such using use book books study studies explores examine examines new one two'.split(' '));
export function tokenize(text){return (text.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().match(/[a-z]+/g)||[]).filter(x=>x.length>2&&!STOP.has(x)).map(stemmer);}
export function bookText(b){return `${b.title} ${b.title} ${b.subtitle} ${b.subtitle} ${b.authors} ${b.subjects.join(' ')} ${b.subjects.join(' ')} ${b.description}`;}
export const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
export function normalize(v){const n=Math.sqrt(dot(v,v));return n?v.map(x=>x/n):v;}
export function createEngine(books,index){
 const lookup=new Map(index.terms.map((x,i)=>[x,i]));
 const docs=books.map(b=>{const tokens=tokenize(bookText(b)),tf={};for(const t of tokens)tf[t]=(tf[t]||0)+1;return {tokens,tf,length:tokens.length};});
 const avg=docs.reduce((s,d)=>s+d.length,0)/docs.length;
 function embed(query){const tf={};for(const t of tokenize(query))if(lookup.has(t))tf[t]=(tf[t]||0)+1;const v=Array(index.dimensions).fill(0);for(const [t,n]of Object.entries(tf)){const i=lookup.get(t),weight=(1+Math.log(n))*index.idf[i];for(let j=0;j<v.length;j++)v[j]+=weight*index.projection[i][j];}return normalize(v);}
 function search(query,{mode='hybrid',subjects=[],from=0,to=9999,author='',sort='relevance',saved=null}={}){
  const terms=[...new Set(tokenize(query))],qv=embed(query),queryPresent=Boolean(query.trim());
  const rows=books.map((b,i)=>{
   let bm25=0;for(const t of terms){const f=docs[i].tf[t]||0,j=lookup.get(t);if(!f||j===undefined)continue;const df=index.df[j],idf=Math.log(1+(books.length-df+.5)/(df+.5));bm25+=idf*f*2.2/(f+1.2*(.25+.75*docs[i].length/avg));}
   const lexical=1-Math.exp(-bm25/8),semantic=Math.max(0,Math.min(1,dot(qv,index.vectors[i]))),score=mode==='keyword'?lexical:mode==='semantic'?semantic:.65*semantic+.35*lexical;
   const matched=terms.filter(t=>docs[i].tf[t]);
   return {book:b,index:i,score,semantic,lexical,bm25,matched,queryPresent};
  }).filter(r=>(!subjects.length||subjects.some(s=>r.book.subjects.includes(s)))&&r.book.year>=from&&r.book.year<=to&&r.book.authors.toLowerCase().includes(author.toLowerCase())&&(!saved||saved.includes(r.book.id))&&(!queryPresent||(mode==='keyword'?r.bm25>0:mode==='semantic'?r.semantic>=.12:r.semantic>=.12||r.bm25>0)));
  rows.sort((a,b)=>sort==='title'?a.book.title.localeCompare(b.book.title):sort==='oldest'?a.book.year-b.book.year:sort==='newest'||!queryPresent?b.book.year-a.book.year:b.score-a.score||b.book.year-a.book.year);
  return {rows,knownTerms:terms.filter(t=>lookup.has(t)),unknownTerms:terms.filter(t=>!lookup.has(t))};
 }
 return {search,embed,similar(id,n=3){const i=books.findIndex(b=>b.id===id);return books.map((book,j)=>({book,score:dot(index.vectors[i],index.vectors[j])})).filter((b,j)=>j!==i).sort((a,b)=>b.score-a.score).slice(0,n);}};
}
