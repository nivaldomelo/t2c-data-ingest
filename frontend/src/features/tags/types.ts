export interface TagLite {
  id: number;
  name: string;
  slug: string;
  color: string | null;
}

export interface Tag extends TagLite {
  description: string | null;
  active: boolean;
  jobs_count: number;
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
}
