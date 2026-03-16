export interface Sentence {
  readonly id: string;
  readonly text: string;
  readonly offsetStart: number;
  readonly offsetEnd: number;
}

export interface Paragraph {
  readonly id: string;
  readonly sentences: readonly Sentence[];
}

export interface DisplayMath {
  readonly id: string;
  readonly latex: string;
}

export interface Table {
  readonly id: string;
  readonly html: string;
}

export interface Figure {
  readonly id: string;
  readonly description: string;
  readonly placeholder: string;
}

export type PageItem = Paragraph | DisplayMath | Table | Figure;

export interface Page {
  readonly id: string;
  readonly items: readonly PageItem[];
}

export interface Document {
  readonly pages: readonly Page[];
}

export function isParagraph(item: PageItem): item is Paragraph {
  return "sentences" in item;
}

export function isDisplayMath(item: PageItem): item is DisplayMath {
  return "latex" in item;
}

export function isTable(item: PageItem): item is Table {
  return "html" in item;
}

export function isFigure(item: PageItem): item is Figure {
  return "description" in item && "placeholder" in item;
}
