import { browser } from '$app/environment';
import { writable } from 'svelte/store';

const TOKEN_KEY = 'signalforge_access_token';

export const accessToken = writable(browser ? localStorage.getItem(TOKEN_KEY) || '' : '');

if (browser) {
  accessToken.subscribe((token) => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  });
}

export function setAccessToken(token: string): void {
  accessToken.set(token);
}

export function clearAccessToken(): void {
  accessToken.set('');
}

export function readAccessToken(): string {
  if (!browser) {
    return '';
  }
  return localStorage.getItem(TOKEN_KEY) || '';
}
