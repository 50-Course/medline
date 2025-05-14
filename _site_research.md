So below is the website tabs accordingly:

**Homepage**

- Main Products Categories: div.sc-19e28ua-1.eZHbVe
  In there belongs a row which has two columns: The Left side (with 7 distinct categories)
  and the right side (same, 7 distinct) - Total of 14.

```
*  The row: div.row__Row-sc-wfit35-0.universGroup__MenuRow-sc-6qd6g7-6.kVmZTr
*  The Columns (Identicals, i belive we should iterate over the parent row):
    - div.column__Column-sc-ztyvp1-0.universGroup__MenuColumn-sc-6qd6g7-7.eaYfnt
    - div.column__Column-sc-ztyvp1-0.universGroup__MenuColumn-sc-6qd6g7-7.eaYfnt
```

- Every Column contains a couple of <li> tags: `li.universGroup__UniverseGroupItemComponent-sc-6qd6g7-3.dTahsv`
- These <li> has a <span> tag (child) in it with: `span.universGroup__UniverseGroupLabel-sc-6qd6g7-10.gKaSAR`
  where we should extract the name/text in between the tabs AS the SECTION/CATEGORY NAME.
- then it should click the dropdown/the list button/button of these tags -
  which would contain a Flex (`#flex`) container of <ul> tag: `ul.universGroup__CategoryUl-sc-6qd6g7-4.iCVouy`
  And in it a couple of Flex items of <li> tags (I think this is inconsequential,
  we can just grab them a tags in it): `li.universGroup__CategoryLi-sc-6qd6g7-8.yUtRm`
  Which has an <a> tag: `a.universGroup__CategoryLink-sc-6qd6g7-9.iUtWKS`

  Now those A tags, we need the:

  - Tag Text (content between the tags)
  - href link (using the href attribute)

- Finally we just follow along the href links into respective individual product pages

**Product Listing Page**

- First we check if this <h1> id category tag (`h1#category`) is the same as our Tag Text?
- Then we find the category group: `div#category-group` which contains some bunch of
  hoverLists objects: `ul.category-grouplist`. We loop through its children <li> nodes:

  -- Each List Node contains: an <a> tag and corresponding image tag <img> (which sits within a `div.imgSubCat`)
  --- For the A tags, we repeat the process as the homepage logic (recursion here, lol): extract the Tag Text, and store a pointer
  to the Link

**Product Detailed Overview Listing Page (Listing Page, but more detailed)**
