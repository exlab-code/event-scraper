<script>
  export let tag;
  export let groupId = null;
  export let selectable = false;
  export let selected = false;
  export let count = null;
  export let onClick = () => {};
  
  // Generate CSS classes
  $: classes = [
    'tag',
    groupId ? `tag-${groupId}` : '',
    selectable ? 'selectable' : '',
    selected ? 'selected' : ''
  ].filter(Boolean).join(' ');
</script>

<button
  class={classes}
  on:click={onClick}
  type="button"
>
  {tag}
  {#if count !== null && count > 1}
    <span class="tag-count ml-2 opacity-70">&nbsp;{count}</span>
  {/if}
</button>
