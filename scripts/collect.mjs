import {load} from 'cheerio';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const run=promisify(execFile), clean=s=>s.replace(/\s+/g,' ').trim();
const revision=process.env.SOURCE_REF||'main';
const base=`https://raw.githubusercontent.com/NYULibraries/dlts-open-square/${revision}/docs/books`;
mkdirSync('.cache/books',{recursive:true});
const get=async url=>(await run('curl',['--fail','--silent','--show-error','--location','--retry','2','--max-time','45',url],{maxBuffer:5e6})).stdout;
const html=process.argv[2]?readFileSync(process.argv[2],'utf8'):await get(`${base}/index.html`);
const $=load(html), books=[];
$('.book-summary').each((i,el)=>{const b=$(el), id=b.find('.book-title-group a').attr('href')?.match(/\d{13}/)?.[0]; if(!id)return;
 books.push({id,title:clean(b.find('.book-title').text()),subtitle:clean(b.find('.book-subtitle').text()),authors:clean(b.find('.author-group').first().text()).replace(/^(By|Edited by)\s+/,''),subjects:b.find('a[href^="/subjects/"]').map((i,x)=>clean($(x).text())).get(),year:Number(b.find('.pubdate').first().text().match(/\d{4}/)?.[0]),language:'English',source:'NYU Press Open Square',sourceUrl:`https://opensquare.nyupress.org/books/${id}/`,sourceMetadataUrl:`${base}/${id}/index.html`,cover:b.find('img').attr('src'),accessStatus:'Open access'});
});
let next=0,done=0; const failures=[];
async function worker(){while(next<books.length){const b=books[next++],path=`.cache/books/${b.id}.html`;try{const h=existsSync(path)?readFileSync(path,'utf8'):await get(b.sourceMetadataUrl);writeFileSync(path,h); const p=load(h);b.description=clean(p('.description').first().text()||p('meta[name="description"]').attr('content')||'').replace(/^\[Open Access\]\s*/,''); if(!b.description)throw Error('Missing description');b.descriptionStatus='Publisher description';}catch(e){b.description='';b.descriptionStatus='Description unavailable';failures.push(b.id);}if(++done%40===0)console.log(`Collected ${done}/${books.length}`);}}
await Promise.all(Array.from({length:6},worker));
writeFileSync('public/data/books.json',JSON.stringify({collectedAt:new Date().toISOString(),sourceRepository:'https://github.com/NYULibraries/dlts-open-square',sourceRef:revision,scope:'Published catalog metadata and publisher descriptions; no book full text ingested.',books},null,2));
console.log(JSON.stringify({books:books.length,descriptions:books.length-failures.length,failures}));
