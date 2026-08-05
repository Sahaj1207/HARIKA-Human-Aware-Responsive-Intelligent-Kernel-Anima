import { apiClient } from './client';

export interface OCRBlockApi {
  text: string;
  category: string;
  confidence: number;
}

export interface OCRResultApi {
  raw_text: string;
  blocks: OCRBlockApi[];
  detected_language: string;
  word_count: number;
  latency_ms: number;
}

export interface ImageAnalysisResultApi {
  classification: string;
  description: string;
  detected_objects: string[];
  dimensions?: { width: number; height: number };
  color_palette: string[];
  confidence: number;
}

export interface PDFPageAnalysisApi {
  page_number: number;
  text: string;
  image_count: number;
  has_tables: boolean;
}


export interface PDFAnalysisResultApi {
  filename: string;
  total_pages: number;
  metadata: Record<string, unknown>;
  pages: PDFPageAnalysisApi[];
  extracted_text: string;
}

export interface CaptionResultApi {
  caption: string;
  detailed_summary: string;
  tags: string[];
}

export interface VisionResultApi {
  id: string;
  filename: string;
  file_type: string;
  provider: string;
  model: string;
  ocr?: OCRResultApi;
  image_analysis?: ImageAnalysisResultApi;
  pdf_analysis?: PDFAnalysisResultApi;
  caption?: CaptionResultApi;
  summary: string;
  latency_ms: number;
  timestamp: string;
}

export interface VisionMetricsApi {
  images_analyzed: number;
  pdfs_processed: number;
  total_ocr_requests: number;
  average_ocr_latency_ms: number;
  average_analysis_time_ms: number;
  failure_rate_percent: number;
  provider_usage: Record<string, number>;
}

export interface VisionHistoryItemApi {
  id: string;
  filename: string;
  file_type: string;
  provider: string;
  model: string;
  latency_ms: number;
  result_summary: string;
  timestamp: string;
}

export const visionService = {
  processImage: async (file: File, provider?: string, model?: string): Promise<VisionResultApi> => {
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
    if (provider) headers['X-Vision-Provider'] = provider;
    if (model) headers['X-Vision-Model'] = model;

    const res = await apiClient.post<VisionResultApi>('/vision/image', formData, { headers });
    return res.data;
  },

  processPdf: async (file: File, provider?: string, model?: string): Promise<VisionResultApi> => {
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
    if (provider) headers['X-Vision-Provider'] = provider;
    if (model) headers['X-Vision-Model'] = model;

    const res = await apiClient.post<VisionResultApi>('/vision/pdf', formData, { headers });
    return res.data;
  },

  extractOcr: async (file: File, provider?: string): Promise<OCRResultApi> => {
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
    if (provider) headers['X-Vision-Provider'] = provider;

    const res = await apiClient.post<OCRResultApi>('/vision/ocr', formData, { headers });
    return res.data;
  },

  getHistory: async (limit = 20): Promise<VisionHistoryItemApi[]> => {
    const res = await apiClient.get<VisionHistoryItemApi[]>(`/vision/history?limit=${limit}`);
    return res.data;
  },

  getMetrics: async (): Promise<VisionMetricsApi> => {
    const res = await apiClient.get<VisionMetricsApi>('/vision/metrics');
    return res.data;
  },
};
