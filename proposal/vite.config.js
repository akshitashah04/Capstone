import {defineConfig} from 'vite';
export default defineConfig({server:{host:'0.0.0.0',port:3001,proxy:{'/api':'http://127.0.0.1:3101'}},build:{outDir:'dist'}});
