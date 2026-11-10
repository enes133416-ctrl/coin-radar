const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('all matching predictions appear, including beyond 150 and in search results', () => {
  const html = fs.readFileSync('docs/index.html', 'utf8');
  const script = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  const elements = {'#q': {value: ''}, '#sort': {value: 'p'}, '#fav': {checked: false}, '#l-up': {}, '#l-dn': {}};
  const context = vm.createContext({
    document: {querySelector: key => elements[key], addEventListener() {}},
    localStorage: {getItem() {return null;}},
    fetch: () => new Promise(() => {}), setInterval() {},
  });
  vm.runInContext(script, context);
  vm.runInContext(`D = {metrics: {up: {base_rate: .01}, dn: {base_rate: .01}},
    coins: Array.from({length: 200}, (_, i) => ({symbol: 'COIN'+i, p_up: .2, p_dn: .1,
      price: 1, chg24: 1, volume: 250000, spark: [1, 2]}))}; render();`, context);
  for (const side of ['#l-up', '#l-dn']) {
    assert.equal((elements[side].innerHTML.match(/class="row"/g) || []).length, 200);
    assert.match(elements[side].innerHTML, /250 Bin \$/);
  }
  elements['#q'].value = 'COIN';
  vm.runInContext('render()', context);
  assert.equal((elements['#l-up'].innerHTML.match(/class="row"/g) || []).length, 200);
  assert.match(elements['#l-up'].innerHTML, /COIN199/);
});
