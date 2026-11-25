import type { ModelKey } from './types';

export interface BrowserModel {
  label: string;
  repo: string;
  revision: string;
  dimensions: number;
  pooling: 'mean' | 'cls';
  queryPrefix: string;
  downloadMb: number;
}

export const DEFAULT_MODEL: ModelKey = 'gte-base';

export const MODELS: Record<ModelKey, BrowserModel> = {
  'e5-small': {
    label: 'E5 small',
    repo: 'Xenova/multilingual-e5-small',
    revision: '761b726dd34fb83930e26aab4e9ac3899aa1fa78',
    dimensions: 384,
    pooling: 'mean',
    queryPrefix: 'query: ',
    downloadMb: 118,
  },
  'e5-base': {
    label: 'E5 base',
    repo: 'onnx-community/multilingual-e5-base-ONNX',
    revision: 'd15bb63d1494d49ff653bb0105592a2696e7a8b6',
    dimensions: 768,
    pooling: 'mean',
    queryPrefix: 'query: ',
    downloadMb: 278,
  },
  'gte-base': {
    label: 'GTE base',
    repo: 'onnx-community/gte-multilingual-base',
    revision: '2edbf5e672aab465f9ed4c154a8b61791c082c69',
    dimensions: 768,
    pooling: 'cls',
    queryPrefix: '',
    downloadMb: 340,
  },
};
