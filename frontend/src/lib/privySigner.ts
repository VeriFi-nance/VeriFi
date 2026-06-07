type PersonalSignFn = (payloadHex: string, address: string) => Promise<string>;

let privySignFn: PersonalSignFn | null = null;

export function setPrivySigner(fn: PersonalSignFn): void {
  privySignFn = fn;
}

export function clearPrivySigner(): void {
  privySignFn = null;
}

export function getPrivySigner(): PersonalSignFn | null {
  return privySignFn;
}
